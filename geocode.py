# -*- coding: utf-8 -*-
"""
Google Geocoding API를 이용한 주소 -> 좌표 변환.

사용 전 환경변수 GOOGLE_MAPS_API_KEY 설정 필요.
Geocoding API를 Google Cloud Console에서 활성화해야 함.
"""

import os
import requests

import config

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GeocodeError(Exception):
    pass


def geocode(query: str, api_key: str = None):
    """자연어 주소/장소명(예: '서울시 강남구 테헤란로 152' 또는 '해운대 호텔')을
    (lat, lng, formatted_address) 튜플로 변환.

    "집"처럼 개인화된 표현은 Google이 이해하지 못하므로, 프로그램 상단에서
    사용자에게 실제 주소나 장소명(호텔명 등)을 입력받는 형태로 UX를 구성해야 함.
    """
    key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY") or config.DEFAULT_GOOGLE_MAPS_API_KEY
    if not key:
        raise GeocodeError(
            "GOOGLE_MAPS_API_KEY가 설정되지 않았습니다 "
            "(환경변수 또는 config.py의 DEFAULT_GOOGLE_MAPS_API_KEY 확인)."
        )

    params = {"address": query, "language": "ko", "region": "kr", "key": key}
    resp = requests.get(GEOCODE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "OK" or not data.get("results"):
        raise GeocodeError(
            f"주소를 찾을 수 없습니다: '{query}' (status={data.get('status')})"
        )

    top = data["results"][0]
    loc = top["geometry"]["location"]
    return loc["lat"], loc["lng"], top["formatted_address"]
