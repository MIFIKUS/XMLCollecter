import xml.etree.ElementTree as ET
import mysql.connector
import requests
import time


connection = None

HEADERS = {'accept-language': 'ru-RU,ru;q=0.9'}

HYPER = ('Hyper', 'Bounty Adrenaline')
TURBO = ('Turbo', 'Hot', 'Hotter', 'Fast', 'The Sprint')
SLOW =  ('Titans', 'The Sunday Marathon')


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
    return requests.get(url, headers=HEADERS).text


while True:
    xml = get_xml()
    root = ET.fromstring(xml)

    ns = {"ns": "http://feed.pokerstars.com/TournamentFeed/2007"}

    for tournament in root.findall("ns:tournament", ns):
        skip = False
        for lobby in tournament.findall("ns:lobby[@type='COM']", ns):
            if lobby.attrib['path'] == 'Tourney:Satellite:All' or lobby.attrib['path'] == 'Tourney:Freeroll':
                skip = True
                break
        game = tournament.find("ns:game", ns).text
        play_money = tournament.attrib.get('play_money')
        if game != "Hold'em" or play_money == 'true' or skip:
            continue
        tournament_id = tournament.attrib['id']
        name = tournament.find("ns:name", ns).text
        gtd = '$' + str(name.replace(' ', '').split(',$')[-1].split('Gtd')[0])
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

        for hyper_string, turbo_string, slow_string in zip(HYPER, TURBO, SLOW):
            if hyper_string in name:
                speed = 'HYPER'
                break
            if turbo_string in name:
                speed = 'TURBO'
                break
            if slow_string in name:
                speed = 'SLOW'
                break
        else:
            speed = 'REG'
        if 'Zoom' in name:
            continue
        if 'mystery' in name.lower() or 'Lotus' in name:
            tournament_type = 'MYSTERY'
        elif 'Bounty Adrenaline' in name or 'Bounty Builder' in name or 'Pacific Rim' in name or 'Progressive KO' in name:
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

        print(output)

        if not is_there_tournament(tournament_id):
            add_tournament(tournament_id, name, gtd, buy_in, total_buy_in, amount_of_players, speed, tournament_type, date)
    print('Турниры кончились')
    time.sleep(1800)
    