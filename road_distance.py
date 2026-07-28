# -*- coding: utf-8 -*-
"""
카카오모빌리티 길찾기(Directions) API로 두 좌표 간 '실제 도로 이동거리'와
'실제 이용 도로명(경로)'을 산출.

Google Directions API는 한국 내 도로 경로(자동차/도보)를 지원하지 않는다
(국내 지리정보 국외반출 제한으로 인한 정책적 제약 - ZERO_RESULTS 반환).
따라서 한국 국내 도로거리는 카카오모빌리티 API를 사용한다.

키 발급: https://developers.kakao.com -> 애플리케이션 추가 -> REST API 키
사용 우선순위: 환경변수 KAKAO_REST_API_KEY -> config.py의 DEFAULT_KAKAO_REST_API_KEY
"""

import os
import requests

# import config

# 카카오모빌리티 길찾기(자동차) API
DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"

# 경로 요약에 포함할 최소 구간 길이(m) - 너무 짧은 이면도로까지 다 나열하면
# 안내가 지저분해지므로, 이 이상인 구간의 도로명만 뽑는다.
MIN_ROAD_SEGMENT_M = 300


class RoutingError(Exception):
    pass


def _get_key(api_key):
    return api_key or os.environ.get("KAKAO_REST_API_KEY") or config.DEFAULT_KAKAO_REST_API_KEY


def _call_directions(origin, destination, api_key=None):
    key = _get_key(api_key)
    if not key:
        raise RoutingError(
            "KAKAO_REST_API_KEY가 설정되지 않았습니다 "
            "(환경변수 또는 config.py의 DEFAULT_KAKAO_REST_API_KEY 확인)."
        )

    lat_o, lng_o = origin
    lat_d, lng_d = destination

    headers = {"Authorization": f"KakaoAK {key}"}
    params = {
        "origin": f"{lng_o},{lat_o}",
        "destination": f"{lng_d},{lat_d}",
        "priority": "RECOMMEND",
    }
    resp = requests.get(DIRECTIONS_URL, headers=headers, params=params, timeout=10)

    if resp.status_code != 200:
        raise RoutingError(
            f"카카오 길찾기 API 오류 (status={resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    routes = data.get("routes", [])
    if not routes or routes[0].get("result_code") != 0:
        msg = routes[0].get("result_msg") if routes else data
        raise RoutingError(f"경로를 찾을 수 없습니다 ({msg})")

    return routes[0]


def driving_distance_km(origin, destination, api_key: str = None) -> float:
    """origin, destination: (lat, lng) 튜플. 반환값: 실제 도로 주행거리(km)."""
    route = _call_directions(origin, destination, api_key)
    return route["summary"]["distance"] / 1000.0


def driving_route(origin, destination, api_key: str = None) -> dict:
    """origin, destination: (lat, lng) 튜플.
    반환값: {"km": float, "roads": [주요 도로명], "duration_seconds": int}

    'roads'는 사람이 읽을 수 있는 경로 요약용이며, 실제 내비게이션 안내
    수준의 정밀도는 아니다 (짧은 이면도로/무명도로는 생략).
    """
    route = _call_directions(origin, destination, api_key)
    km = route["summary"]["distance"] / 1000.0
    duration_seconds = route["summary"].get("duration", 0)

    roads = []
    for section in route.get("sections", []):
        for road in section.get("roads", []):
            name = (road.get("name") or "").strip()
            distance = road.get("distance", 0)
            if not name or distance < MIN_ROAD_SEGMENT_M:
                continue
            if not roads or roads[-1] != name:
                roads.append(name)

    return {"km": km, "roads": roads, "duration_seconds": duration_seconds}
