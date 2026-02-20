SYNONYMS = {
    "국물": ["탕", "찌개", "전골", "라멘", "샤브"],
    "탕": ["국물", "찌개", "전골"],
    "찌개": ["국물", "탕", "전골"],
    "고기": ["구이", "스테이크", "바베큐"],
    "면": ["국수", "라멘", "우동", "파스타"],
}


def expand_query(query: str) -> list[str]:
    q = query.strip().lower()
    expanded = [q]
    expanded.extend(SYNONYMS.get(q, []))
    return list(dict.fromkeys(expanded))
