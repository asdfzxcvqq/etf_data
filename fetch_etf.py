"""네이버 금융 ETF 목록 데이터 수집 모듈.

이 모듈은 네이버 금융 Sise API에서 ETF 품목 목록 데이터를 가져와
지정한 폴더(`etf_data/`)에 CSV 파일 형태로 저장하는 기능을 제공합니다.
매분 또는 주기적인 스케줄러를 통해 실행할 수 있습니다.
"""

import os
import json
from datetime import datetime
from typing import Optional
import requests
import pandas as pd


def fetch_and_save_etf_data() -> Optional[str]:
    """네이버 금융 API로부터 ETF 목록을 가져와 CSV 파일로 저장합니다.

    Returns:
        Optional[str]: 저장된 타임스탬프 CSV 파일의 상대 경로. 실패 시 None 반환.

    Raises:
        requests.RequestException: API 네트워크 요청 실패 시 발생.
    """
    # 네이버 금융 ETF 목록 API URL
    url: str = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0&targetColumn=market_sum&sortOrder=desc"
    
    # 봇 차단 방지를 위한 User-Agent 설정
    headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    # API HTTP 요청 실행
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # 네이버 금융 API 응답 인코딩(EUC-KR) 처리 후 JSON 변환
    response.encoding = 'euc-kr'
    data: dict = response.json()
    
    # JSON 구조에서 ETF 아이템 리스트 추출
    etf_items: list[dict] = data.get("result", {}).get("etfItemList", [])
    if not etf_items:
        print("[Warning] ETF 데이터를 불러오지 못했거나 목록이 비어있습니다.")
        return None
    
    # 데이터프레임 변환
    df: pd.DataFrame = pd.DataFrame(etf_items)
    
    # 현재 수집 시간 기록 컬럼 추가
    now: datetime = datetime.now()
    df['collected_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # CSV 저장 폴더 생성 (없을 경우 자동 생성)
    output_dir: str = "etf_data"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 타임스탬프가 포함된 고유 CSV 파일 생성
    timestamp_filename: str = os.path.join(output_dir, f"etf_items_{now.strftime('%Y%m%d_%H%M%S')}.csv")
    df.to_csv(timestamp_filename, index=False, encoding='utf-8-sig')
    
    # 2. 가장 최근 데이터 덮어쓰기 파일 생성
    latest_filename: str = os.path.join(output_dir, "etf_items_latest.csv")
    df.to_csv(latest_filename, index=False, encoding='utf-8-sig')
    
    print(f"[{df['collected_at'].iloc[0]}] 총 {len(df)}개 ETF 항목 저장 완료: '{timestamp_filename}'")
    return timestamp_filename


if __name__ == "__main__":
    fetch_and_save_etf_data()
