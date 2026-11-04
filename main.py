import re
from collections import Counter
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="급식 규칙 찾기", layout="wide")
st.title("🍱 급식 메뉴 연관 규칙 분석")


# 1. 데이터 불러오기 및 전처리
@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"
    df = pd.read_csv(url, encoding="utf-8")

    transactions = []
    all_menus = set()

    for raw_menu in df["메뉴"].dropna():
        # 세로줄(|)로 분리
        items = raw_menu.split("|")
        cleaned_items = set()
        for item in items:
            # 괄호 및 괄호 안 내용 제거 (예: "쌀밥(초등)" -> "쌀밥")
            cleaned = re.sub(r"\(.*?\)", "", item).strip()
            if cleaned:
                cleaned_items.add(cleaned)

        if cleaned_items:
            transactions.append(cleaned_items)
            all_menus.update(cleaned_items)

    return transactions, sorted(list(all_menus))


transactions, all_menus = load_data()
total_tx = len(transactions)


# 2. 연관 규칙 및 각 메뉴별 등장을 수 계산
@st.cache_data
def calculate_rules(transactions, total_tx):
    item_counts = Counter()
    pair_counts = Counter()

    for tx in transactions:
        for item in tx:
            item_counts[item] += 1
        for pair in combinations(sorted(tx), 2):
            pair_counts[pair] += 1

    rules = []
    for (item_a, item_b), count_ab in pair_counts.items():
        count_a = item_counts[item_a]
        count_b = item_counts[item_b]

        # A -> B 규칙
        support_ab = count_ab / total_tx
        confidence_ab = count_ab / count_a
        lift_ab = confidence_ab / (count_b / total_tx)

        rules.append(
            {
                "조건": item_a,
                "결과": item_b,
                "동시": count_ab,
                "지지도": round(support_ab, 4),
                "신뢰도": round(confidence_ab, 4),
                "향상도": round(lift_ab, 4),
            }
        )

        # B -> A 규칙 (순서 바꾼 규칙)
        confidence_ba = count_ab / count_b
        lift_ba = confidence_ba / (count_a / total_tx)

        rules.append(
            {
                "조건": item_b,
                "결과": item_a,
                "동시": count_ab,
                "지지도": round(support_ab, 4),
                "신뢰도": round(confidence_ba, 4),
                "향상도": round(lift_ba, 4),
            }
        )

    return pd.DataFrame(rules), len(pair_counts), item_counts, pair_counts


rules_df, total_pairs_count, item_counts, pair_counts = calculate_rules(
    transactions, total_tx
)

# 3. 사이드바 컨트롤러 (필터 및 정렬)
st.sidebar.header("필터 및 정렬 설정")

selected_menu = st.sidebar.selectbox(
    "메뉴 선택 (선택 시 해당 메뉴가 포함된 규칙만 표시)",
    ["전체 보기"] + all_menus,
)

min_cooccur = st.sidebar.slider(
    "최소 동시 일수 선택",
    min_value=1,
    max_value=10,
    value=1,
    step=1,
)

sort_option = st.sidebar.radio(
    "정렬 기준 선택", ["향상도", "신뢰도", "동시"], index=0
)

# 4. 데이터 필터링 및 정렬
filtered_df = rules_df.copy()

# 최소 동시 일수 필터링
filtered_df = filtered_df[filtered_df["동시"] >= min_cooccur]

# 특정 메뉴 필터링
if selected_menu != "전체 보기":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
    ]

filtered_df = filtered_df.sort_values(by=sort_option, ascending=False)

# 5. 요약 정보 및 필터링 결과 출력
st.markdown(
    f"**급식 일수:** {total_tx}일 &nbsp;|&nbsp; "
    f"**메뉴 종류 수:** {len(all_menus)}개 &nbsp;|&nbsp; "
    f"**함께 나온 적이 있는 메뉴 쌍의 수:** {total_pairs_count}쌍"
)

st.info(
    f"🔍 **필터 적용 결과:** 현재 표에 남은 연관 규칙은 **{len(filtered_df)}개**입니다. (최소 동시 일수: {min_cooccur}일 이상)"
)

# 6. 연관 규칙 표 출력
st.subheader("📋 연관 규칙 표")
st.dataframe(filtered_df, use_container_width=True)

# 7. Plotly 가로 막대그래프 (향상도 상위 10개)
st.subheader("📊 향상도 Top 10 규칙")

top10_df = filtered_df.sort_values(by="향상도", ascending=False).head(10)

if not top10_df.empty:
    top10_df["규칙"] = top10_df["조건"] + " ➔ " + top10_df["결과"]

    fig = px.bar(
        top10_df.sort_values(by="향상도", ascending=True),
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        labels={"향상도": "향상도 (Lift)", "규칙": "규칙 (조건 ➔ 결과)"},
        title=f"향상도 상위 10개 규칙 ({selected_menu})",
    )

    fig.update_traces(texttemplate="%{text:.4f}", textposition="outside")
    fig.update_layout(height=450, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("표시할 연관 규칙 데이터가 없습니다.")

st.divider()

# 8. 함께 나온 적 없는 짝 화면
st.subheader("❌ 함께 나온 적 없는 짝 찾기")
st.write(
    "선택한 메뉴와 한 번도 같이 나오지 않았지만, 단독으로 10일 이상 나온 메뉴 목록입니다."
)

target_menu = st.selectbox(
    "조회할 대상 메뉴 선택",
    all_menus,
    key="unpaired_menu_select",
)

target_days = item_counts[target_menu]
st.write(f"📌 **'{target_menu}'** 이(가) 급식에 나온 날 수: **{target_days}일**")

# 선택한 메뉴와 함께 나온 적 있는 다른 메뉴들 수집
co_occurring_menus = set()
for (item_a, item_b), count in pair_counts.items():
    if count > 0:
        if item_a == target_menu:
            co_occurring_menus.add(item_b)
        elif item_b == target_menu:
            co_occurring_menus.add(item_a)

# 조건 만족 메뉴 추출: (1) 한 번도 같이 나온 적 없음 (2) 혼자 10일 이상 등장
unpaired_list = []
for menu, count in item_counts.items():
    if menu != target_menu and menu not in co_occurring_menus and count >= 10:
        unpaired_list.append({"메뉴": menu, "단독 등장 일수": count})

unpaired_df = pd.DataFrame(unpaired_list)

if not unpaired_df.empty:
    unpaired_df = unpaired_df.sort_values(by="단독 등장 일수", ascending=False)
    st.dataframe(unpaired_df, use_container_width=True)
else:
    st.info(
        f"'{target_menu}'와(과) 함께 나온 적 없으면서 10일 이상 나온 메뉴가 없습니다."
    )
