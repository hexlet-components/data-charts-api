import os

import requests

PORT = os.getenv('PORT')


def test_server():
    response = requests.get('http://localhost:4000/')
    assert response.status_code == 200
    assert response.json()['status'] == 'It Works'

    response = requests.get('http://localhost:4000/visits?begin=2023-03-01&end=2023-03-02')
    assert response.status_code == 200
    assert response.json()[0] == {
        "datetime": "2023-03-01T10:36:22",
        "platform": "web",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.6"
        ),
        "visit_id": "1de9ea66-70d3-4a1f-8735-df5ef7697fb9"
    }
