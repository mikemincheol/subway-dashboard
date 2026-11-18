import pandas as pd
import plotly.express as px
import streamlit as st

PAY_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/subway_pay.csv"
TIME_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/subway_time.csv"

BLUE = "#2a78d6"
ORANGE = "#eb6834"

st.set_page_config(page_title="서울 지하철 대시보드", layout="wide")


def clean_common(df: pd.DataFrame) -> pd.DataFrame:
    """1~9호선만 남기고(9호선2~3단계 등은 9호선으로 통합), 역 이름의 괄호를 제거한다."""
    line = df["호선명"].str.extract(r"^([1-9])호선", expand=False)
    df = df.loc[line.notna()].copy()
    df["호선명"] = line[line.notna()] + "호선"
    df["역명"] = (
        df["지하철역"]
        .str.replace(r"\(.*?\)", "", regex=True)
        .str.strip()
    )
    df["월"] = pd.to_datetime(df["사용월"].astype(str), format="%Y%m")
    return df


@st.cache_data(show_spinner="유무임 승하차 데이터를 불러오는 중...")
def load_pay() -> pd.DataFrame:
    df = pd.read_csv(PAY_URL)
    return clean_common(df)


@st.cache_data(show_spinner="시간대별 승하차 데이터를 불러오는 중...")
def load_time() -> pd.DataFrame:
    df = pd.read_csv(TIME_URL)
    return clean_common(df)


def style_bar(fig, color, height=None):
    fig.update_traces(marker_color=color, marker_line_width=0)
    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title=None, autorange="reversed"),
        bargap=0.35,
    )
    if height:
        fig.update_layout(height=height)
    return fig


pay = load_pay()
time_df = load_time()

st.title("서울 지하철 데이터 대시보드")
st.caption("서울 지하철 1~9호선 기준이며, 역 이름의 괄호 표기는 제거해 정리했습니다.")

tab1, tab2, tab3 = st.tabs(["무임 비율 순위", "시간대별 1위", "10년 변화"])

# ---------------------------------------------------------------- 탭 1
with tab1:
    latest = pay["월"].max()
    st.subheader("무임승차 비율이 높은 역")
    st.caption(f"기준월 {latest:%Y년 %m월} / 무임 비율 = 무임승차 ÷ (유임승차 + 무임승차)")

    c1, c2 = st.columns([3, 1])
    top_n = c1.slider("상위 몇 개 역을 볼까요", min_value=5, max_value=50, value=20, step=1)
    merge = c2.checkbox("환승역 합치기", value=True,
                        help="체크하면 같은 이름의 역을 호선 구분 없이 합산하고, 해제하면 호선별로 나눠 봅니다.")

    cur = pay[pay["월"] == latest]
    keys = ["역명"] if merge else ["역명", "호선명"]
    g = cur.groupby(keys, as_index=False)[["유임승차인원", "무임승차인원"]].sum()
    g["전체승차"] = g["유임승차인원"] + g["무임승차인원"]
    g = g[g["전체승차"] > 0]
    g["무임비율"] = g["무임승차인원"] / g["전체승차"] * 100
    g["표시명"] = g["역명"] if merge else g["역명"] + " (" + g["호선명"] + ")"

    top = g.sort_values("무임비율", ascending=False).head(top_n)
    fig = px.bar(
        top, x="무임비율", y="표시명", orientation="h",
        custom_data=["무임승차인원", "전체승차"],
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>무임 비율 %{x:.1f}%<br>"
                      "무임승차 %{customdata[0]:,}명<br>전체 승차 %{customdata[1]:,}명<extra></extra>"
    )
    style_bar(fig, BLUE, height=max(400, top_n * 24 + 80))
    fig.update_xaxes(title="무임 비율 (%)", ticksuffix="%")
    st.plotly_chart(fig, width="stretch")

    with st.expander("표로 보기"):
        st.dataframe(
            top[["표시명", "무임승차인원", "전체승차", "무임비율"]]
            .rename(columns={"표시명": "역", "전체승차": "전체 승차", "무임비율": "무임 비율(%)"})
            .round({"무임 비율(%)": 1}),
            hide_index=True, width="stretch",
        )

# ---------------------------------------------------------------- 탭 2
with tab2:
    latest_t = time_df["월"].max()
    st.subheader("시간대별 승차·하차 1위 역")
    st.caption(f"기준월 {latest_t:%Y년 %m월} / 환승역은 호선을 합산한 역 단위 기준")

    hour = st.slider("시간대 (시작 시각)", min_value=0, max_value=23, value=8, step=1, format="%d시")
    label = f"{hour:02d}시-{hour + 1:02d}시"
    st.markdown(f"#### {label}")

    cur_t = time_df[time_df["월"] == latest_t]
    on_col, off_col = f"{label} 승차인원", f"{label} 하차인원"
    gt = cur_t.groupby("역명", as_index=False)[[on_col, off_col]].sum()

    left, right = st.columns(2)
    for col, name, value_col, color in [
        (left, "승차", on_col, BLUE),
        (right, "하차", off_col, ORANGE),
    ]:
        top10 = gt.sort_values(value_col, ascending=False).head(10)
        with col:
            if top10.empty or top10[value_col].max() <= 0:
                st.info("이 시간대에는 데이터가 없습니다.")
                continue
            best = top10.iloc[0]
            st.metric(f"{name} 1위", best["역명"], f"{int(best[value_col]):,}명", delta_color="off")
            f = px.bar(top10, x=value_col, y="역명", orientation="h")
            f.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,}명<extra></extra>")
            style_bar(f, color, height=420)
            f.update_xaxes(title=f"{name} 인원 (명)")
            f.update_layout(title=dict(text=f"{name} 상위 10개 역", font=dict(size=14)))
            st.plotly_chart(f, width="stretch")

# ---------------------------------------------------------------- 탭 3
with tab3:
    st.subheader("역별 월간 유동 인구 변화")
    st.caption("유동 인구 = 월간 승차 + 하차 인원 (유임 + 무임 합산, 환승역은 호선 합산)")

    stations = sorted(pay["역명"].unique())
    default_idx = stations.index("강남") if "강남" in stations else 0
    station = st.selectbox("역 선택", stations, index=default_idx)

    s = pay[pay["역명"] == station].copy()
    s["유동인구"] = (s["유임승차인원"] + s["무임승차인원"]
                  + s["유임하차인원"] + s["무임하차인원"])
    monthly = s.groupby("월", as_index=False)["유동인구"].sum().sort_values("월")

    fig3 = px.line(monthly, x="월", y="유동인구")
    fig3.update_traces(
        line=dict(color=BLUE, width=2),
        hovertemplate="%{x|%Y년 %m월}<br>%{y:,}명<extra></extra>",
    )
    fig3.update_layout(
        title=dict(text=f"{station}역 월별 유동 인구", font=dict(size=14)),
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        height=450,
    )
    fig3.update_xaxes(title=None)
    fig3.update_yaxes(title="월간 승하차 인원 (명)", tickformat=",")
    st.plotly_chart(fig3, width="stretch")
