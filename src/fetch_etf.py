"""네이버 금융 ETF 목록 데이터 실시간 수집 및 JSON/CSV 저장 모듈.

이 모듈은 네이버 금융 Sise API에서 ETF 품목 목록 데이터를 안전하게 수집하여
지정한 데이터 폴더(`data/`)에 JSON 및 CSV 파일 형태로 저장합니다.
네트워크 타임아웃 및 해외 IP 접속 블록 방지를 위해 재시도(Retry) 매커니즘과
예외 방어 로직이 내장되어 있습니다.
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import pandas as pd


def fetch_and_save_etf_data() -> Optional[str]:
    """네이버 금융 API로부터 ETF 목록을 안정적으로 수집하여 data/ 폴더에 저장합니다.

    Returns:
        Optional[str]: 저장된 최신 JSON 파일의 상대 경로. 실패 시 None 반환.

    Raises:
        requests.RequestException: 모든 네트워크 요청 재시도 실패 시 발생.
    """
    url: str = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0&targetColumn=market_sum&sortOrder=desc"
    
    # 봇 차단 및 타임아웃 방지를 위한 헤더 구성
    headers: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://finance.naver.com/sise/etf.naver",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    output_dir: str = "data"
    os.makedirs(output_dir, exist_ok=True)
    latest_json_path: str = os.path.join(output_dir, "latest.json")
    latest_csv_path: str = os.path.join(output_dir, "etf_items_latest.csv")

    # 세션 객체 생성 및 백오프 재시도(Retry) 정책 적용
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        # API HTTP 요청 실행 (connect timeout: 5초, read timeout: 15초)
        response = session.get(url, headers=headers, timeout=(5, 15))
        response.raise_for_status()
        
        # 네이버 금융 API 응답 인코딩(EUC-KR) 처리 후 JSON 변환
        response.encoding = 'euc-kr'
        raw_data: Dict[str, Any] = response.json()
        etf_items: list[dict] = raw_data.get("result", {}).get("etfItemList", [])
        
        if not etf_items:
            print("[Warning] API 응답의 ETF 데이터 목록이 비어있습니다.")
            return None
        
        df: pd.DataFrame = pd.DataFrame(etf_items)
        now_str: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df['collected_at'] = now_str

        # 카테고리 매핑
        tab_code_map = {
            1: '국내 대표지수', 2: '국내 업종/테마', 3: '국내 파생',
            4: '해외 주식', 5: '원자재/원자재파생', 6: '채권/금리', 7: '기타'
        }
        df['category'] = df['etfTabCode'].map(tab_code_map).fillna('기타/미분류')

        # 1. JSON 형태로 data/latest.json 저장
        output_payload = {
            "fetched_at": now_str,
            "total_count": len(df),
            "items": df.to_dict(orient="records")
        }
        with open(latest_json_path, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, ensure_ascii=False, indent=2)

        # 2. CSV 형태로 data/etf_items_latest.csv 저장
        df.to_csv(latest_csv_path, index=False, encoding='utf-8-sig')

        print(f"[{now_str}] 성공적으로 {len(df)}개 ETF 데이터를 수집 및 저장했습니다.")
        return latest_json_path

    except (requests.RequestException, Exception) as e:
        print(f"[Error] 네이버 API 수집 중 네트워크 타임아웃/오류 발생: {e}")
        
        # 기존 저장된 로컬 data/latest.json 이 존재하는지 확인 후 백업 로드
        if os.path.exists(latest_json_path):
            print(f"[Info] 기존 로컬 저장 파일 '{latest_json_path}'을 보존합니다.")
            return latest_json_path
        else:
            raise e


if __name__ == "__main__":
    fetch_and_save_etf_data()
