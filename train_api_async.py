# -*- coding: utf-8 -*-
"""
국토교통부 TAGO 열차정보 API - 비동기 버전 (asyncio + aiohttp)

get_all_train_info_async(): 3개 등급(KTX/무궁화/새마을) 동시 호출
→ 약 15초 → 5초로 단축 (병렬 처리)
"""

import os
import asyncio
import aiohttp
import functools
from datetime import datetime, timedelta

# Streamlit의 asyncio 루프와 호환되도록 설정
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # nest_asyncio 미설치 시 무시 (로컬에서만 필요)


TAGO_BASE_URL = "https://apis.data.go.kr/1613000/TrainInfo"
TRAIN_GRADE_MAP = {
    "ktx": "00",
    "saemaul": "01",
    "mugunghwa": "02",
}

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
    
    # 2. 주요 역에 없으면 API로 조회 (동기)
    key = _get_key(api_key)
    if not key:
        return ""

    import requests
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


async def _fetch_train_info_async(session, dep_place_id, arr_place_id, grade_code, api_key, dep_date="null"):
    """비동기 열차 정보 조회 - 소요시간 + 열차 정보 반환."""
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
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return {"duration": 0, "trains": []}
            
            data = await resp.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            if not items:
                return {"duration": 0, "trains": []}

            min_duration = float('inf')
            trains = []
            
            for train in items:
                dep_time = _parse_time(train.get("depplandtime", ""))
                arr_time = _parse_time(train.get("arrplandtime", ""))
                
                if dep_time > 0 and arr_time > 0:
                    duration = arr_time - dep_time
                    if duration > 0:
                        if duration < min_duration:
                            min_duration = duration
                        
                        trains.append({
                            "trainno": train.get("trainno", ""),
                            "traingradename": train.get("traingradename", ""),
                            "deptime": train.get("depplandtime", "")[8:14],  # HHMMSS → HH:MM
                            "arrtime": train.get("arrplandtime", "")[8:14],
                            "duration": duration,
                            "fare": train.get("adultcharge", 0),
                        })
            
            return {
                "duration": int(min_duration) if min_duration != float('inf') else 0,
                "trains": sorted(trains, key=lambda x: x["duration"])  # 빠른 순서로 정렬
            }
    except Exception as e:
        print(f"비동기 API 오류: {e}")
        return {"duration": 0, "trains": []}


async def get_all_train_info_async(station_dep: str, station_arr: str, api_key: str = None, dep_date: str = "null") -> dict:
    """3개 등급(KTX/무궁화/새마을) 동시 조회 - 비동기 버전
    
    Returns:
        {
            "ktx": {"duration": 7200, "trains": [...]},
            "mugunghwa": {"duration": 9000, "trains": [...]},
            "saemaul": {"duration": 8400, "trains": [...]},
        }
    """
    dep_place_id = _get_station_id(station_dep, api_key)
    arr_place_id = _get_station_id(station_arr, api_key)
    
    if not dep_place_id or not arr_place_id:
        return {"ktx": {"duration": 0, "trains": []}, 
                "mugunghwa": {"duration": 0, "trains": []},
                "saemaul": {"duration": 0, "trains": []}}

    key = _get_key(api_key)
    if not key:
        return {"ktx": {"duration": 0, "trains": []}, 
                "mugunghwa": {"duration": 0, "trains": []},
                "saemaul": {"duration": 0, "trains": []}}

    # 비동기 HTTP 세션 생성
    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_train_info_async(session, dep_place_id, arr_place_id, "00", key, dep_date),  # KTX
            _fetch_train_info_async(session, dep_place_id, arr_place_id, "02", key, dep_date),  # 무궁화
            _fetch_train_info_async(session, dep_place_id, arr_place_id, "01", key, dep_date),  # 새마을
        ]
        
        # 3개 요청 동시 실행
        results = await asyncio.gather(*tasks)
    
    return {
        "ktx": results[0],
        "mugunghwa": results[1],
        "saemaul": results[2],
    }


def get_all_train_info_sync(station_dep: str, station_arr: str, api_key: str = None, dep_date: str = "null") -> dict:
    """동기 래퍼 - nest_asyncio로 Streamlit 호환성 확보"""
    try:
        return asyncio.run(get_all_train_info_async(station_dep, station_arr, api_key, dep_date))
    except Exception as e:
        print(f"비동기 API 실패: {e}")
        # 오류 발생 시 빈 결과 반환
        return {"ktx": {"duration": 0, "trains": []}, 
                "mugunghwa": {"duration": 0, "trains": []},
                "saemaul": {"duration": 0, "trains": []}}
