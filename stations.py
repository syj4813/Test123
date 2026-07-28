# -*- coding: utf-8 -*-
"""
주요 철도역 좌표 DB (스타터 셋 - 필요시 data/stations.csv 로 확장/교체 가능).
좌표는 대표 좌표(역사 위치) 근사값이며, 정밀 배차/편의 계산이 아닌
'출발지 -> 최근접역' 자차 이동거리 계산용 후보 선정에 사용됨.

주의: 이 좌표만으로는 부족함. 실제로는
  1) 이 DB로 후보 역 K개(예: 반경 50km 이내)를 추린 뒤
  2) 각 후보에 대해 Directions API로 실제 도로거리를 계산해 최솟값 선택
하는 방식을 권장 (직선거리로 최근접을 정하면 산맥/강 때문에 오차 발생 가능).
"""

import csv
import math
import os

_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "stations.csv")

# 스타터 DB: (역명, 위도, 경도, 노선구분)
# 노선구분: ktx / mugunghwa / saemaul (해당 역에 정차하는 열차 종류, 복수 가능은 별도 행)
_STARTER = [
    ("서울역", 37.5546, 126.9707, "ktx"),
    ("용산역", 37.5299, 126.9648, "ktx"),
    ("영등포역", 37.5157, 126.9070, "saemaul"),
    ("광명역", 37.4183, 126.8849, "ktx"),
    ("수원역", 37.2662, 127.0001, "saemaul"),
    ("천안아산역", 36.7952, 127.1049, "ktx"),
    ("오송역", 36.6208, 127.3287, "ktx"),
    ("대전역", 36.3315, 127.4342, "ktx"),
    ("김천구미역", 36.1298, 128.3134, "ktx"),
    ("동대구역", 35.8792, 128.6284, "ktx"),
    ("경주역", 35.8383, 129.2075, "ktx"),
    ("울산역", 35.5641, 129.1128, "ktx"),
    ("부산역", 35.1152, 129.0415, "ktx"),
    ("광주송정역", 35.1373, 126.7936, "ktx"),
    ("목포역", 34.7936, 126.3845, "saemaul"),
    ("여수엑스포역", 34.7472, 127.7457, "mugunghwa"),
    ("전주역", 35.8425, 127.1237, "saemaul"),
    ("익산역", 35.9432, 126.9550, "ktx"),
    ("순천역", 34.9506, 127.4890, "mugunghwa"),
    ("포항역", 36.1216, 129.3742, "ktx"),
    ("강릉역", 37.7636, 128.9010, "ktx"),
    ("청량리역", 37.5804, 127.0466, "mugunghwa"),
    ("평택역", 36.9922, 127.0868, "saemaul"),
    ("마산역", 35.2103, 128.5811, "mugunghwa"),
    ("진주역", 35.1963, 128.1114, "mugunghwa"),
]


def _load():
    if os.path.exists(_CSV_PATH):
        rows = []
        with open(_CSV_PATH, encoding="utf-8") as f:
            for r in csv.reader(f):
                rows.append((r[0], float(r[1]), float(r[2]), r[3]))
        return rows
    return _STARTER


STATIONS = _load()


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_stations(lat, lng, k=3, line_filter=None):
    """직선거리 기준 최근접 역 k개 후보 반환 [(name, lat, lng, line, straight_km), ...]
    실제 최종 선택은 road_distance로 각 후보의 도로거리를 구해 최솟값을 쓸 것.
    """
    candidates = STATIONS
    if line_filter:
        candidates = [s for s in candidates if s[3] == line_filter]
    scored = [
        (name, slat, slng, line, _haversine_km(lat, lng, slat, slng))
        for name, slat, slng, line in candidates
    ]
    scored.sort(key=lambda x: x[4])
    return scored[:k]
