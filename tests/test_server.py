import os

import requests

PORT = os.getenv('PORT', '4000')
BASE_URL = f'http://localhost:{PORT}'


def test_index():
    response = requests.get(f'{BASE_URL}/')
    assert response.status_code == 200
    assert response.json()['status'] == 'It Works'


def test_visits():
    response = requests.get(
        f'{BASE_URL}/visits?begin=2023-03-01&end=2023-03-02'
    )
    assert response.status_code == 200

    records = response.json()
    assert len(records) > 0

    # Запись ищется по идентификатору, а не берётся по индексу: у запроса нет
    # ORDER BY, поэтому порядок строк ничем не задан. Проверка на records[0]
    # держалась на случайном совпадении и сломалась, когда порядок изменился.
    expected = {
        "datetime": "2023-03-01T10:36:22",
        "platform": "web",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.6"
        ),
        "visit_id": "1de9ea66-70d3-4a1f-8735-df5ef7697fb9"
    }
    found = [r for r in records if r['visit_id'] == expected['visit_id']]
    assert found == [expected]


def test_visits_empty_range():
    # Пустая выборка должна оставаться разбираемым JSON. Раньше отдавалось
    # "[]]", и клиент падал на разборе там, где данных просто нет.
    response = requests.get(
        f'{BASE_URL}/visits?begin=2000-01-01&end=2000-01-02'
    )
    assert response.status_code == 200
    assert response.json() == []


def test_registrations():
    response = requests.get(
        f'{BASE_URL}/registrations?begin=2023-03-01&end=2023-03-02'
    )
    assert response.status_code == 200

    records = response.json()
    assert len(records) > 0
    assert set(records[0]) == {
        'datetime', 'user_id', 'email', 'platform', 'registration_type',
    }
