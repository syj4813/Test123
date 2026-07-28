# -*- coding: utf-8 -*-
"""
주요 고속/시외버스터미널 좌표 DB (스타터 셋).
stations.py와 동일한 방식 - 직선거리로 후보를 추리고, 최종 거리는
road_distance.driving_distance_km으로 실제 도로거리를 재계산해야 함.
"""

import csv
import math
import os

_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "terminals.csv")

# (터미널명, 위도, 경도)
_STARTER = [
    ("서울고속버스터미널(경부/영동선)", 37.5045, 127.0046),
    ("서울센트럴시티터미널(호남선)", 37.5047, 127.0048),
    ("동서울종합터미널", 37.5347, 127.0947),
    ("수원버스터미널", 37.2755, 127.0161),
    ("대전복합터미널", 36.3325, 127.4288),
    ("동대구고속버스터미널", 35.8797, 128.6294),
    ("부산종합버스터미널(노포동)", 35.2130, 129.0866),
    ("광주광역시고속버스터미널(유스퀘어)", 35.1601, 126.8853),
    ("전주고속버스터미널", 35.8324, 127.1310),
    ("강릉시외/고속버스터미널", 37.7522, 128.8977),
    ("춘천고속버스터미널", 37.8763, 127.7373),
    ("포항고속버스터미널", 36.0424, 129.3652),
    ("울산고속버스터미널", 35.5478, 129.3312),
    ("마산고속버스터미널", 35.2138, 128.5715),
    ("진주고속버스터미널", 35.1802, 128.1075),
    ("목포종합버스터미널", 34.7994, 126.4114),
]


def _load():
    if os.path.exists(_CSV_PATH):
        rows = []
        with open(_CSV_PATH, encoding="utf-8") as f:
            for r in csv.reader(f):
                rows.append((r[0], float(r[1]), float(r[2])))
        return rows
    return _STARTER


TERMINALS = _load()


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_terminals(lat, lng, k=3):
    scored = [
        (name, tlat, tlng, _haversine_km(lat, lng, tlat, tlng))
        for name, tlat, tlng in TERMINALS
    ]
    scored.sort(key=lambda x: x[3])
    return scored[:k]
