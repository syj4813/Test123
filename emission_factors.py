# -*- coding: utf-8 -*-
"""
탄소집약도.xlsx 기반 이동수단별 배출계수.

- 자동차: km당 '차량 전체' 배출량 (5인승 기준, 인원수와 무관하게 차량 1대 기준)
- 버스/열차: km당 '탑승인원 1명당' 배출량 (인원수를 곱해야 총량이 됨)

원본 시트 값 (2013/2010년 기준):
    탄소 (kg CO2eq/km)      미세먼지 (kg PM2.5eq/km)
자동차(5인승)   0.27978              0.00013
고속버스        0.05472/인           2.34718e-5/인
무궁화호        0.08054/인           2.72769e-5/인
새마을호        0.04196/인           1.53201e-5/인
KTX            0.03810/인           1.99560e-5/인
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmissionFactor:
    co2_per_km: float          # kg CO2eq
    pm25_per_km: float         # kg PM2.5eq
    per_passenger: bool        # True면 탑승인원을 곱해야 함


FACTORS = {
    "car": EmissionFactor(0.27978, 0.00013, per_passenger=False),
    "express_bus": EmissionFactor(0.05472, 2.34718e-5, per_passenger=True),
    "mugunghwa": EmissionFactor(0.08054, 2.72769e-5, per_passenger=True),
    "saemaul": EmissionFactor(0.04196, 1.53201e-5, per_passenger=True),
    "ktx": EmissionFactor(0.03810, 1.99560e-5, per_passenger=True),
}


CAR_CAPACITY = 5  # 배출계수가 가정하는 승용차 1대 최대 탑승인원


def compute_emission(mode: str, km: float, passengers: int = 1):
    """mode별 km에 대한 총 배출량(kg CO2eq, kg PM2.5eq) 반환.

    - 자동차: 5인승 기준 배출계수이므로, 인원수가 5명을 넘으면
      ceil(인원수/5)대의 차량이 필요하다고 보고 그만큼 배출량을 곱한다.
      (예: 6명 -> 2대, 10명 -> 2대, 11명 -> 3대)
    - 버스/열차: 좌석 1인당 배출계수이므로 인원수를 그대로 곱한다.
    """
    import math

    f = FACTORS[mode]
    if f.per_passenger:
        multiplier = passengers
    else:
        multiplier = max(1, math.ceil(passengers / CAR_CAPACITY))

    return {
        "co2_kg": f.co2_per_km * km * multiplier,
        "pm25_kg": f.pm25_per_km * km * multiplier,
    }
