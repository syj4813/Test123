# -*- coding: utf-8 -*-
"""
Google Geocoding API로 자연어 주소/장소명을 좌표로 변환.
"""

import os
import requests

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GeocodeError(Exception):
    pass


def geocode(query: str, api_key: str = None):
    """자연어 주소/장소명(예: '서울시 강남구 테헤란로 152')을
    (lat, lng, formatted_address) 튜플로 변환.
    """
    try:
        import streamlit as st
        key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY") or st.secrets.get("GOOGLE_MAPS_API_KEY")
    except:
        key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
    
    if not key:
        raise GeocodeError("GOOGLE_MAPS_API_KEY가 설정되지 않았습니다.")

    params = {"address": query, "language": "ko", "region": "kr", "key": key}
    resp = requests.get(GEOCODE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "OK" or not data.get("results"):
        raise GeocodeError(
            f"주소를 찾을 수 없습니다: '{query}' (status={data.get('status')})"
        )

    result = data["results"][0]
    lat = result["geometry"]["location"]["lat"]
    lng = result["geometry"]["location"]["lng"]
    formatted_address = result.get("formatted_address", query)
    return lat, lng, formatted_address
