import xml.etree.ElementTree as ET
import mysql.connector
import requests
import time
import traceback
from string import ascii_letters, digits


connection = None

HEADERS = {'accept-language': 'ru-RU,ru;q=0.9'}

HYPER = ('Hyper', 'Bounty Adrenaline')
TURBO = ('Turbo', 'Hot', 'Hotter', 'Fast', 'The Sprint', 'Friday Rounder', 'Mystery Bounty $5.50')
SLOW =  ('Titans', 'The Sunday Marathon', 'Marathon')


def get_cursor() -> mysql.connector.connect().cursor:
    global connection
    if connection is None or not connection.is_connected():
        connection = mysql.connector.connect(
            host='147.78.67.17',
            user='poker',
            password='root'
        )
        connection.autocommit = True

    return connection.cursor()


def is_there_tournament(tournament_id) -> bool:
    query = f'SELECT * FROM poker.xml WHERE tournament_id = "{tournament_id}"'
    cursor = get_cursor()
    cursor.execute(query)
    if len(cursor.fetchall()):
        return True
    return False

def add_tournament(tournament_id, name, gtd, buy_in, total_buy_in, amount_of_players, speed, tournament_type, date):
    query = f'INSERT INTO poker.xml (tournament_id, name, gtd, buy_in, total_buy_in, amount_of_players, speed, type, date, create_date) VALUES ("{tournament_id}", "{name}", "{gtd}", "{buy_in}", "{total_buy_in}", {amount_of_players}, "{speed}", "{tournament_type}", "{date}", NOW());'
    print(query)
    cursor = get_cursor()
    cursor.execute(query)


def get_xml() -> str:
    """Получает XML с сайта"""
    url = 'https://www.pokerstars.net/datafeed_global/tournaments/all.xml'
    return requests.get(url, headers=HEADERS, verify=False).text


def fix_name(name: str) -> str:
    """Фиксит запятые в имени"""
    index = 0
    new_name = ''
    for _ in range(len(name)):
        if index + 1 <= len(name):
            if name[index] == ',':
                if name[index+1] in ascii_letters or name[index+1] in digits:
                    new_name += ', '

                else:
                    new_name += name[index]
            else:
                new_name += name[index]
        index += 1

    return new_name


def fix_comma_in_db():
    query = "UPDATE poker.xml SET name = REPLACE(NAME, '$1, 050', '$1,050');"
    cursor = get_cursor()
    cursor.execute(query)


def fix_number_commas_in_db():
    """Исправляет запятые в числовых значениях (убирает пробелы после запятых)"""
    queries = [
        "UPDATE poker.xml SET name = REPLACE(NAME, ', 000', ',000');",
        "UPDATE poker.xml SET name = REPLACE(NAME, ', 100', ',100');",
        "UPDATE poker.xml SET name = REPLACE(NAME, ', 200', ',200');",
        "UPDATE poker.xml SET name = REPLACE(name, ', 300', ',300');"
    ]
    cursor = get_cursor()
    for query in queries:
        cursor.execute(query)


tournaments_to_load = []

while True:
   try:
       xml = get_xml()
       root = ET.fromstring(xml)

       ns = {"ns": "http://feed.pokerstars.com/TournamentFeed/2007"}

       for tournament in root.findall("ns:tournament", ns):
            try:
                skip = False
                for lobby in tournament.findall("ns:lobby[@type='COM']", ns):
                    if lobby.attrib['path'] == 'Tourney:Freeroll':
                        skip = True
                        break
                game = tournament.find("ns:game", ns).text
                play_money = tournament.attrib.get('play_money')
                if game != "Hold'em" or play_money == 'true' or skip:
                    continue
                tournament_id = tournament.attrib['id']
                name = tournament.find("ns:name", ns).text
                try:
                     gtd = '$' + str(name.replace(' ', '').split(',$')[-1].split('Gtd')[0])
                except:
                     gtd = '0'

                name = name.split(', $')
                if len(name) > 1:
                    name = ', $'.join(name[:-1])
                else:
                    name = ''.join(name).replace('  ', '').split(',$')[0]

                date = tournament.find("ns:start_date", ns).text
                buy_in = tournament.find("ns:buy_in_fee", ns).text
                buy_in_values = buy_in.replace('$', '').replace(' ', '').split('+')

                # Преобразуем каждое значение в целое число и суммируем
                total_buy_in_value = sum(float(value) for value in buy_in_values)

                if total_buy_in_value.is_integer():
                    total_buy_in_value = int(total_buy_in_value)
                    total_buy_in = f'${total_buy_in_value}'
                else:
                    total_buy_in = f'${total_buy_in_value:.2f}'
                # Форматируем итоговую строку

                amount_of_players = tournament.find("ns:max_table_players", ns).text

                speed = None

                for hyper_string in HYPER:
                    if hyper_string in name:
                        speed = 'HYPER'
                        break

                # Если в первом цикле ничего не найдено, проверяем TURBO
                if speed is None:
                    for turbo_string in TURBO:
                        if turbo_string in name:
                            speed = 'TURBO'
                            break

                # Если и в TURBO ничего не найдено, проверяем SLOW
                if speed is None:
                    for slow_string in SLOW:
                        if slow_string in name:
                            speed = 'SLOW'
                            break
                if speed is None:
                    speed = 'REG'
                #if 'Zoom' in name or 'Seats' in name or 'Phase' in name:
                #    continue
                if 'mystery' in name.lower() or 'Lotus' in name:
                    tournament_type = 'MYSTERY'
                elif 'Bounty Adrenaline' in name or 'Bounty Builder' in name or 'Pacific Rim' in name or 'Progressive KO' in name or 'Bear Fury' in name or 'Anaconda' in name or "Saturday KO" in name or "Mini Sunday Million" in name or 'Thursday Thrill' in name:
                    tournament_type = 'KO'
                else:
                    tournament_type = 'FREEZE'

                output = (
                    f"Tournament ID: {tournament_id}\n"
                    f"Name: {name}\n"
                    f"Date: {date}\n"
                    f"Game: {game}\n"
                    f"Buy-in: {buy_in}\n"
                    f"Total Buy-in: {total_buy_in}\n"
                    f"Max Players: {amount_of_players}\n"
                    f"Speed: {speed}\n"
                    f"Tournament Type: {tournament_type}\n"
                )

                name = fix_name(name)
                print(output)

                tournaments_to_load.append((tournament_id, name, gtd, buy_in, total_buy_in, amount_of_players, speed, tournament_type, date))

                for i in tournaments_to_load:
                     tournament_id, name, gtd, buy_in, total_buy_in, amount_of_players, speed, tournament_type, date = i
                     if not is_there_tournament(tournament_id):
                         add_tournament(tournament_id, name, gtd, buy_in, total_buy_in, amount_of_players, speed, tournament_type, date)

            except Exception as e:
                traceback.print_exc()
       print('Турниры кончились')
       fix_comma_in_db()
       fix_number_commas_in_db()
       tournaments_to_load = []
       time.sleep(900)
   except Exception as e:
       traceback.print_exc()
       print(e)
