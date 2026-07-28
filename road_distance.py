# -*- coding: utf-8 -*-
"""
카카오모빌리티 길찾기(Directions) API로 도로거리와 경로를 산출.
"""

import os
import requests

DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"
MIN_ROAD_SEGMENT_M = 300


class RoutingError(Exception):
    pass


def _get_key(api_key):
    try:
        import streamlit as st
        return api_key or os.environ.get("KAKAO_REST_API_KEY") or st.secrets.get("KAKAO_REST_API_KEY")
    except:
        return api_key or os.environ.get("KAKAO_REST_API_KEY")


def _call_directions(origin, destination, api_key=None):
    key = _get_key(api_key)
    if not key:
        raise RoutingError(
            "KAKAO_REST_API_KEY가 설정되지 않았습니다."
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
    route = _call_directions(origin, destination, api_key)
    return route["summary"]["distance"] / 1000.0


def driving_route(origin, destination, api_key: str = None) -> dict:
    route = _call_directions(origin, destination, api_key)
    km = route["summary"]["distance"] / 1000.0

    roads = []
    for section in route.get("sections", []):
        for road in section.get("roads", []):
            name = (road.get("name") or "").strip()
            distance = road.get("distance", 0)
            if not name or distance < MIN_ROAD_SEGMENT_M:
                continue
            if not roads or roads[-1] != name:
                roads.append(name)

    return {"km": km, "roads": roads}
