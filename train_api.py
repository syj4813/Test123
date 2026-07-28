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

# 주요 역 ID (TAGO 시스템)
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
    """역명으로 역ID 조회. 주요 역은 즉시 반환, 나머지는 API 조회.
    
    Args:
        station_name: 역 이름 (예: "서울역", "서울")
        api_key: TAGO API 키
    
    Returns:
        역ID (예: "NAT010000"). 찾지 못하면 빈 문자열
    """
    # 1. 주요 역 먼저 확인 (API 호출 안 함)
    for major_name, station_id in MAJOR_STATIONS.items():
        if major_name.lower() in station_name.lower() or station_name.lower() in major_name.lower():
            return station_id
    
    # 2. 주요 역에 없으면 API로 조회
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
def _fetch_train_info(dep_place_id: str, arr_place_id: str, grade_code: str, api_key: str, dep_date: str = "null") -> int:
    """캐시된 열차 정보 조회.
    
    Args:
        dep_date: 출발 날짜 (YYYYMMDD 형식, "null"이면 오늘)
    """
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


def get_nearest_train(station_dep: str, station_arr: str, train_grade: str, dep_time_str: str = None, api_key: str = None) -> dict:
    """선택한 시간에 가장 가까운 열차 정보 조회.
    
    Args:
        station_dep: 출발역 이름
        station_arr: 도착역 이름
        train_grade: 열차 등급 ("ktx", "saemaul", "mugunghwa")
        dep_time_str: 원하는 출발시간 (HH:MM 형식, None이면 현재시간)
        api_key: TAGO API 키
    
    Returns:
        {
            "train_no": "1234",
            "dep_time": "09:30",
            "arr_time": "11:45",
            "duration_minutes": 135,
            "fare": 45000
        }
        실패 시 빈 딕셔너리
    """
    from datetime import datetime, timedelta
    
    # 역명 → 역ID (캐시됨)
    dep_place_id = _get_station_id(station_dep, api_key)
    arr_place_id = _get_station_id(station_arr, api_key)
    
    if not dep_place_id or not arr_place_id:
        return {}

    key = _get_key(api_key)
    if not key:
        return {}

    grade_code = TRAIN_GRADE_MAP.get(train_grade)
    if not grade_code:
        return {}

    # 원하는 시간 파싱
    if dep_time_str:
        try:
            target_time = datetime.strptime(dep_time_str, "%H:%M").time()
        except:
            target_time = datetime.now().time()
    else:
        target_time = datetime.now().time()

    url = f"{TAGO_BASE_URL}/GetStrtpntAlocFndTrainInfo"
    params = {
        "serviceKey": key,
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
            return {}
        data = resp.json()
    except:
        return {}

    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not items:
        return {}

    # 가장 가까운 열차 찾기
    nearest_train = None
    min_diff = float('inf')
    
    for train in items:
        dep_time_str_api = train.get("depplandtime", "")
        arr_time_str_api = train.get("arrplandtime", "")
        
        if not dep_time_str_api or len(dep_time_str_api) < 14:
            continue
        
        try:
            dep_hour = int(dep_time_str_api[8:10])
            dep_min = int(dep_time_str_api[10:12])
            train_time = datetime.strptime(f"{dep_hour:02d}:{dep_min:02d}", "%H:%M").time()
            
            # 타겟 시간과의 차이 계산
            target_dt = datetime.combine(datetime.today(), target_time)
            train_dt = datetime.combine(datetime.today(), train_time)
            
            # 지나간 열차면 다음 날로 계산
            if train_dt < target_dt:
                train_dt += timedelta(days=1)
            
            diff = (train_dt - target_dt).total_seconds()
            
            if diff >= 0 and diff < min_diff:
                min_diff = diff
                
                # 도착시간 파싱
                arr_hour = int(arr_time_str_api[8:10])
                arr_min = int(arr_time_str_api[10:12])
                duration = int(arr_time_str_api[:14]) - int(dep_time_str_api[:14])
                if duration < 0:
                    duration += 240000  # 자정 넘어가는 경우
                duration_seconds = int(duration / 10000) * 3600 + (int((duration % 10000) / 100)) * 60
                
                nearest_train = {
                    "train_no": train.get("trainno", ""),
                    "train_grade": train.get("traingradename", train_grade),
                    "dep_time": f"{dep_hour:02d}:{dep_min:02d}",
                    "arr_time": f"{arr_hour:02d}:{arr_min:02d}",
                    "duration_minutes": duration_seconds // 60,
                    "fare": train.get("adultcharge", 0),
                    "wait_minutes": int(min_diff // 60)  # 현재시간으로부터 분 단위 대기시간
                }
        except:
            continue
    
    return nearest_train if nearest_train else {}
    """실제 열차 소요시간(초) 조회.
    
    Args:
        station_dep: 출발역 이름 (예: "서울")
        station_arr: 도착역 이름 (예: "부산")
        train_grade: 열차 등급 ("ktx", "saemaul", "mugunghwa")
        api_key: TAGO API 키
        dep_date: 출발 날짜 (YYYYMMDD 형식, "null"이면 오늘)
    
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
    return _fetch_train_info(dep_place_id, arr_place_id, grade_code, key, dep_date)
