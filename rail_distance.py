# -*- coding: utf-8 -*-
"""
역간 '실제 선로거리' 산출 - 한국철도공사 공식 '철도운행거리' 데이터 기반.

data/rail_edges.csv 는 코레일이 공개한 노선별 역간거리표
(한국철도공사_철도운행거리_전체_20240901.xlsx)를 파싱해서 만든
'인접역 간 거리' 엣지 목록이다 (역A,역B,km). 이 인접거리들을 그래프로
쌓고, 두 역 사이의 실제 선로거리는 다익스트라 최단경로 합산으로 구한다.

왜 이런 방식이 필요한가:
- 도로 라우팅 API(Google Directions 등)는 도로망 기준이라 철도 선로거리와
  전혀 다르다.
- 코레일 원본 데이터는 노선별로 나뉘어 있어(경부, 호남, 경전, 중앙 등),
  서로 다른 노선에 있는 두 역 사이의 거리는 표에 직접 나와 있지 않다.
  예: 서울(경부선)에서 강릉(경강선)까지는 표 한 장으로 안 나옴.
  -> 공유되는 접속역(오송, 동대구, 청량리 등)을 거쳐가는 최단경로를
    그래프 탐색으로 복원해야 한다.

수도권 광역전철 전용 시트(과천/분당/일산, 수인, 서해)는 원본 파싱에서
제외했다. 이유: 이 시트들은 KTX/무궁화/새마을 중장거리 비교에 기여가
없고, 지방 노선과 동일한 역명(예: '구룡' - 분당선 구룡역 vs 경전선의
동명 역)이 존재해 그래프를 잘못 이어버리는 위험이 있었다.
"""

import csv
import heapq
import math
import os
from collections import defaultdict

_EDGES_PATH = os.path.join(os.path.dirname(__file__), "data", "rail_edges.csv")

TORTUOSITY_FACTOR = 1.15  # 그래프에 역이 없을 때만 쓰는 최후의 근사치


def _normalize(name: str) -> str:
    """'서울역' -> '서울' 처럼 원본 데이터(접미사 '역' 없음)와 표기를 맞춘다."""
    name = name.strip()
    if name.endswith("역") and len(name) > 1:
        name = name[:-1]
    return name


def _load_graph():
    graph = defaultdict(dict)  # graph[a][b] = km
    if not os.path.exists(_EDGES_PATH):
        return graph
    with open(_EDGES_PATH, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 3:
                continue
            a, b, km = row[0].strip(), row[1].strip(), float(row[2])
            graph[a][b] = km
            graph[b][a] = km
    return graph


_GRAPH = _load_graph()


def _dijkstra(start, end):
    """반환: (거리km, 경유역 리스트) 또는 연결 안되면 None"""
    if start not in _GRAPH or end not in _GRAPH:
        return None
    if start == end:
        return 0.0, [start]
    dist = {start: 0.0}
    prev = {}
    pq = [(0.0, start)]
    visited = set()
    while pq:
        d, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        if node == end:
            path = [node]
            while path[-1] != start:
                path.append(prev[path[-1]])
            path.reverse()
            return d, path
        for nxt, w in _GRAPH[node].items():
            nd = d + w
            if nxt not in dist or nd < dist[nxt]:
                dist[nxt] = nd
                prev[nxt] = node
                heapq.heappush(pq, (nd, nxt))
    return None  # 그래프 상 연결 안 됨


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def station_to_station_km(name_a, lat_a, lng_a, name_b, lat_b, lng_b):
    """반환: (km, is_approx: bool, via_stations: list[str])
    is_approx=True 면 코레일 공식 데이터에 해당 역이 없어 근사치를 썼다는 뜻
    (반드시 사용자에게 고지할 것). 이 경우 via_stations는 [name_a, name_b]만 담김.

    via_stations는 선로상 실제 경유 경로이며, 열차가 그 역들에 '정차'한다는
    뜻은 아니다 (완행 구간 등 모든 역이 포함될 수 있음).
    """
    na, nb = _normalize(name_a), _normalize(name_b)
    result = _dijkstra(na, nb)
    if result is not None:
        km, path = result
        return km, False, path

    straight = _haversine_km(lat_a, lng_a, lat_b, lng_b)
    return straight * TORTUOSITY_FACTOR, True, [na, nb]
