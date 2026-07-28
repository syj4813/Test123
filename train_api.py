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
from datetime import datetime, timedelta


TAGO_BASE_URL = "https://apis.data.go.kr/1613000/TrainInfo"
TRAIN_GRADE_MAP = {
    "ktx": "00",
    "saemaul": "01",
    "mugunghwa": "02",
}

# 주요 역 ID (TAGO 시스템) - API 호출 줄이기 위함
MAJOR_STATIONS = {
    "서울": "NAT010000",
    "부산": "NAT010971",
    "대구": "NAT010502",
    "대전": "NAT010204",
    "광주": "NAT010814",
    "울산": "NAT011057",
    "천안": "NAT010182",
    "수원": "NAT010058",
    "청주": "NAT010395",
    "전주": "NAT010687",
    "원주": "NAT010289",
    "강릉": "NAT010625",
    "속초": "NAT010684",
    "포항": "NAT010571",
    "목포": "NAT010902",
    "여수": "NAT010930",
    "순천": "NAT010865",
    "나주": "NAT010834",
    "익산": "NAT010725",
    "김제": "NAT010714",
}


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
    """역명으로 역ID 조회. 주요 역은 즉시 반환, 나머지는 API 조회."""
    # 1. 주요 역 먼저 확인 (API 호출 안 함)
    for major_name, station_id in MAJOR_STATIONS.items():
        if major_name.lower() in station_name.lower() or station_name.lower() in major_name.lower():
            return station_id
    
    # 2. 주요 역에 없으면 API로 조회
    key = _get_key(api_key)
    if not key:
        return ""

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
                stn_name = station.get("stationname", "").strip()
                if stn_name.lower() == station_name.lower() or station_name in stn_name:
                    return station.get("stationid", "")
        except:
            continue
    
    return ""


@functools.lru_cache(maxsize=500)
def _fetch_train_info(dep_place_id: str, arr_place_id: str, grade_code: str, api_key: str, dep_date: str = "null") -> int:
    """캐시된 열차 정보 조회 - 소요시간 반환."""
    url = f"{TAGO_BASE_URL}/GetStrtpntAlocFndTrainInfo"
    params = {
        "serviceKey": api_key,
        "pageNo": 1,
        "numOfRows": 100,
        "_type": "json",
        "depPlaceId": dep_place_id,
        "arrPlaceId": arr_place_id,
        "depPlandTime": dep_date,
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


def get_train_duration(station_dep: str, station_arr: str, train_grade: str, api_key: str = None, dep_date: str = "null") -> int:
    """실제 열차 소요시간(초) 조회."""
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

    return _fetch_train_info(dep_place_id, arr_place_id, grade_code, key, dep_date)
