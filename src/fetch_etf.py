"""네이버 금융 ETF 목록 데이터 실시간 수집 및 JSON/CSV 저장 모듈.

이 모듈은 네이버 금융 Sise API에서 ETF 품목 목록 데이터를 수집하여
지정한 데이터 폴더(`data/`)에 JSON 및 CSV 파일 형태로 저장합니다.
GitHub Actions 워크플로우나 로컬 스케줄러에 의해 주기적으로 실행될 수 있습니다.
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
import requests
import pandas as pd


def fetch_and_save_etf_data() -> Optional[str]:
    """네이버 금융 API로부터 ETF 목록을 수집하여 data/ 폴더에 JSON 및 CSV로 저장합니다.

    Returns:
        Optional[str]: 저장된 최신 JSON 파일의 상대 경로. 실패 시 None 반환.

    Raises:
        requests.RequestException: API 네트워크 요청 실패 시 발생.
    """
    url: str = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0&targetColumn=market_sum&sortOrder=desc"
    
    # 봇 차단 방지를 위한 User-Agent 설정
    headers: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    # API HTTP 요청 실행
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    # 네이버 금융 API 응답 인코딩(EUC-KR) 처리 후 JSON 변환
    response.encoding = 'euc-kr'
    raw_data: Dict[str, Any] = response.json()
    
    etf_items: list[dict] = raw_data.get("result", {}).get("etfItemList", [])
    if not etf_items:
        print("[Warning] ETF 데이터를 불러오지 못했거나 목록이 비어있습니다.")
        return None
    
    df: pd.DataFrame = pd.DataFrame(etf_items)
    
    # 현재 수집 시간 기록 추가
    now: datetime = datetime.now()
    now_str: str = now.strftime("%Y-%m-%d %H:%M:%S")
    df['collected_at'] = now_str
    
    # 카테고리 탭 매핑
    tab_code_map = {
        1: '국내 대표지수',
        2: '국내 업종/테마',
        3: '국내 파생',
        4: '해외 주식',
        5: '원자재/원자재파생',
        6: '채권/금리',
        7: '기타'
    }
    df['category'] = df['etfTabCode'].map(tab_code_map).fillna('기타/미분류')

    # 저장 디렉터리 생성 (글로벌 룰 준수: data/)
    output_dir: str = "data"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. JSON 형태 저장 (GitHub Pages 프론트엔드 소비용)
    output_payload = {
        "fetched_at": now_str,
        "total_count": len(df),
        "items": df.to_dict(orient="records")
    }
    
    latest_json_path: str = os.path.join(output_dir, "latest.json")
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
        
    # 2. CSV 형태 저장
    latest_csv_path: str = os.path.join(output_dir, "etf_items_latest.csv")
    df.to_csv(latest_csv_path, index=False, encoding='utf-8-sig')
    
    print(f"[{now_str}] 총 {len(df)}개 ETF 항목 저장 완료: '{latest_json_path}' 및 '{latest_csv_path}'")
    return latest_json_path


if __name__ == "__main__":
    fetch_and_save_etf_data()
