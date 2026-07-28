# -*- coding: utf-8 -*-
"""
국토교통부 TAGO 열차정보 API로 실제 열차 소요시간 조회.

GetStrtpntAlocFndTrainInfo: 출/도착지기반 열차 조회
응답: 각 열차의 출발시간(depplandtime), 도착시간(arrplandtime)
소요시간 = (도착시간 - 출발시간)의 최소값 (가장 빠른 열차 기준)
"""

import os
import requests
import functools
from datetime import datetime


TAGO_BASE_URL = "https://apis.data.go.kr/1613000/TrainInfo"
TRAIN_GRADE_MAP = {
    "ktx": "00",
    "saemaul": "01",
    "mugunghwa": "02",
}


class TrainAPIError(Exception):
    pass


def _get_key(api_key):
    """API 키 우선순위: 인자 → 환경변수 → Streamlit Secrets."""
    try:
        import streamlit as st
        return api_key or os.environ.get("TAGO_API_KEY") or st.secrets.get("TAGO_API_KEY")
    except:
        return api_key or os.environ.get("TAGO_API_KEY")


def _parse_time(time_str: str) -> int:
    """YYYYMMDDhhmmss 형식을 초(seconds)로 변환."""
    if not time_str or len(time_str) < 14:
        return 0
    try:
        dt = datetime.strptime(time_str, "%Y%m%d%H%M%S")
        return int(dt.timestamp())
    except:
        return 0


@functools.lru_cache(maxsize=500)
def _get_station_id(station_name: str, api_key: str = None) -> str:
    """역명으로 역ID 조회.
    
    Args:
        station_name: 역 이름 (예: "서울역", "서울")
        api_key: TAGO API 키
    
    Returns:
        역ID (예: "NAT010000"). 찾지 못하면 빈 문자열
    """
    key = _get_key(api_key)
    if not key:
        return ""

    # 모든 시/도 코드 (11=서울, 26=부산, 등)
    city_codes = ["11", "26", "27", "28", "29", "30", "31", "36", "37", "39"]
    
    for city_code in city_codes:
        url = f"{TAGO_BASE_URL}/GetCtyAcctoTrainSttnList"
        params = {
            "serviceKey": key,
            "pageNo": 1,
            "numOfRows": 1000,
            "_type": "json",
            "cityCode": city_code,
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                continue
            
            data = resp.json()
            stations = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            for station in stations:
                # 역명이 정확히 일치하거나 포함되는 경우
                stn_name = station.get("stationname", "").strip()
                if stn_name.lower() == station_name.lower() or station_name in stn_name:
                    return station.get("stationid", "")
        except:
            continue
    
    return ""


@functools.lru_cache(maxsize=500)
def _fetch_train_info(dep_place_id: str, arr_place_id: str, grade_code: str, api_key: str) -> int:
    """캐시된 열차 정보 조회."""
    url = f"{TAGO_BASE_URL}/GetStrtpntAlocFndTrainInfo"
    params = {
        "serviceKey": api_key,
        "pageNo": 1,
        "numOfRows": 100,
        "_type": "json",
        "depPlaceId": dep_place_id,
        "arrPlaceId": arr_place_id,
        "depPlandTime": "null",
        "trainGradeCode": grade_code,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return 0
        data = resp.json()
    except:
        return 0

    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not items:
        return 0

    min_duration = float('inf')
    for train in items:
        dep_time = _parse_time(train.get("depplandtime", ""))
        arr_time = _parse_time(train.get("arrplandtime", ""))
        
        if dep_time > 0 and arr_time > 0:
            duration = arr_time - dep_time
            if duration > 0 and duration < min_duration:
                min_duration = duration

    return int(min_duration) if min_duration != float('inf') else 0


def get_train_duration(station_dep: str, station_arr: str, train_grade: str, api_key: str = None) -> int:
    """실제 열차 소요시간(초) 조회.
    
    Args:
        station_dep: 출발역 이름 (예: "서울")
        station_arr: 도착역 이름 (예: "부산")
        train_grade: 열차 등급 ("ktx", "saemaul", "mugunghwa")
        api_key: TAGO API 키
    
    Returns:
        소요시간(초). 조회 실패 시 0 반환
    """
    # 역명 → 역ID (캐시됨)
    dep_place_id = _get_station_id(station_dep, api_key)
    arr_place_id = _get_station_id(station_arr, api_key)
    
    if not dep_place_id or not arr_place_id:
        return 0

    key = _get_key(api_key)
    if not key:
        return 0

    grade_code = TRAIN_GRADE_MAP.get(train_grade)
    if not grade_code:
        return 0

    # 캐시된 함수로 조회
    return _fetch_train_info(dep_place_id, arr_place_id, grade_code, key)
