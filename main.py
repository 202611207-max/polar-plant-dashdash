import io
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(page_title="극지식물 생육 대시보드", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CSV 읽기 (인코딩 이중 시도)
# ─────────────────────────────────────────────
@st.cache_data
def read_csv(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# ─────────────────────────────────────────────
# 열 이름 표준화 (KeyError 방지)
# ─────────────────────────────────────────────
def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").
                str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce"
            )
            if num.notna().mean() >= 0.5:
                df[c] = num
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df

# ─────────────────────────────────────────────
# 그래프 헬퍼
# ─────────────────────────────────────────────
def styled_fig(fig):
    fig.update_layout(
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
        margin=dict(l=40, r=20, t=30, b=40),
    )
    return fig

def scatter_with_trend(x, y, xlabel, ylabel, title):
    df = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(df) < 2:
        st.info(f"📈 {title}: 추세선을 그릴 데이터가 부족해요.")
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["x"], y=df["y"], mode="markers",
                             name="데이터점", marker=dict(size=8)))
    slope, intercept = np.polyfit(df["x"], df["y"], 1)
    x_line = np.linspace(df["x"].min(), df["x"].max(), 100)
    y_line = slope * x_line + intercept
    fig.add_trace(go.Scatter(x=x_line, y=y_line, mode="lines",
                             name=f"추세선 (y={slope:.2f}x+{intercept:.1f})",
                             line=dict(color="coral", width=2)))
    r = np.corrcoef(df["x"], df["y"])[0, 1]
    fig.update_layout(title=title, xaxis_title=xlabel, yaxis_title=ylabel)
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper",
                       text=f"상관계수 r = {r:.3f}", showarrow=False,
                       font=dict(size=13, color="darkslategray"))
    return styled_fig(fig)

# ─────────────────────────────────────────────
# 사이드바: 파일 업로드
# ─────────────────────────────────────────────
st.sidebar.title("🌱 데이터 업로드")
env_file = st.sidebar.file_uploader("환경 CSV 파일", type="csv")
growth_file = st.sidebar.file_uploader("생육 결과 CSV 파일", type="csv")

school_name = ""
if env_file is not None:
    school_name = os.path.basename(env_file.name).split("_")[0]
elif growth_file is not None:
    school_name = os.path.basename(growth_file.name).split("_")[0]

st.sidebar.markdown("---")
st.sidebar.info("📌 인코딩(utf-8-sig/cp949)과 열 이름이 달라도 자동 처리됩니다.")

# ─────────────────────────────────────────────
# 데이터 로드 (사이드바에서 한 번만)
# ─────────────────────────────────────────────
env_df = pd.DataFrame()
growth_df = pd.DataFrame()

if env_file is not None:
    with st.spinner("환경 데이터를 읽는 중..."):
        env_df = std_cols(read_csv(env_file))

if growth_file is not None:
    with st.spinner("생육 결과 데이터를 읽는 중..."):
        growth_df = std_cols(read_csv(growth_file))

# ─────────────────────────────────────────────
# 탭 구성
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# ─────────────────────────────────────────────
# Tab 1: 실험 개요
# ─────────────────────────────────────────────
with tab1:
    try:
        st.title(f"🌱 {school_name} 극지식물 개체별 생육 차이 분석")
        st.caption("극지식물은 척박한 환경에서 살아남는 식물로, 같은 조건에서도 개체마다 생육 차이가 큽니다.")

        st.header("🔬 연구 배경 및 목적")
        st.markdown("""
- **연구 배경**: 극지식물은 온도·습도·pH·EC 등 환경 요인이 생육에 큰 영향을 줍니다.
- **연구 목적**: 우리 학교 극지식물 개체들의 생육 상태(생중량, 잎 수, 길이)를 비교하여
  어떤 개체가 잘 자랐는지, 환경과의 관계는 어떠한지 분석합니다.
- **분석 항목**: 평균·표준편차·변동계수(CV), 상관계수, 상위/하위 25% 비교
        """)

        st.header("📋 데이터 요약")
        summary_rows = []

        if not growth_df.empty and "개체번호" in growth_df.columns:
            n_ind = growth_df["개체번호"].nunique()
            summary_rows.append(["총 개체 수", f"{n_ind}개"])
        else:
            summary_rows.append(["총 개체 수", "CSV 미업로드"])

        if not env_df.empty and "time" in env_df.columns:
            t_min = env_df["time"].min()
            t_max = env_df["time"].max()
            if pd.notna(t_min) and pd.notna(t_max):
                summary_rows.append(["측정 기간",
                    f"{t_min.strftime('%Y-%m-%d')} ~ {t_max.strftime('%Y-%m-%d')}"])
            else:
                summary_rows.append(["측정 기간", "날짜 정보 부족"])
        else:
            summary_rows.append(["측정 기간", "CSV 미업로드"])

        env_cols_avail = [c for c in ["temperature", "humidity", "ph", "ec"]
                          if c in env_df.columns]
        summary_rows.append(["환경 측정 항목",
                             ", ".join(env_cols_avail) if env_cols_avail else "없음"])

        growth_cols_avail = [c for c in ["잎 수", "지상부 길이", "지하부 길이", "생중량"]
                              if c in growth_df.columns]
        summary_rows.append(["생육 측정 항목",
                             ", ".join(growth_cols_avail) if growth_cols_avail else "없음"])

        st.table(pd.DataFrame(summary_rows, columns=["항목", "내용"]))

        st.header("📊 주요 지표")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if not growth_df.empty and "개체번호" in growth_df.columns:
                st.metric("총 개체수", f"{growth_df['개체번호'].nunique()}개")
            else:
                st.metric("총 개체수", "N/A")

        with col2:
            if not env_df.empty and "temperature" in env_df.columns:
                vals = pd.to_numeric(env_df["temperature"], errors="coerce").dropna()
                if len(vals) >= 1:
                    st.metric("평균 온도", f"{vals.mean():.1f}°C")
                else:
                    st.metric("평균 온도", "데이터 부족")
            else:
                st.metric("평균 온도", "CSV 미업로드")

        with col3:
            if not env_df.empty and "humidity" in env_df.columns:
                vals = pd.to_numeric(env_df["humidity"], errors="coerce").dropna()
                if len(vals) >= 1:
                    st.metric("평균 습도", f"{vals.mean():.1f}%")
                else:
                    st.metric("평균 습도", "데이터 부족")
            else:
                st.metric("평균 습도", "CSV 미업로드")

        with col4:
            if not growth_df.empty and "생중량" in growth_df.columns:
                vals = pd.to_numeric(growth_df["생중량"], errors="coerce").dropna()
                if len(vals) >= 1:
                    st.metric("평균 생중량", f"{vals.mean():.1f}g")
                else:
                    st.metric("평균 생중량", "데이터 부족")
            else:
                st.metric("평균 생중량", "CSV 미업로드")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ─────────────────────────────────────────────
# Tab 2: 환경 데이터
# ─────────────────────────────────────────────
with tab2:
    try:
        st.header("🌡️ 환경 데이터 분석")

        if env_df.empty:
            st.info("📁 환경 CSV 파일을 업로드하면 여기 내용이 표시됩니다.")
        else:
            env_num_cols = [c for c in ["temperature", "humidity", "ph", "ec"]
                            if c in env_df.columns]

            if env_num_cols:
                st.subheader("📈 환경 지표 요약 (평균·최소·최대)")
                summary_data = []
                for col in env_num_cols:
                    vals = pd.to_numeric(env_df[col], errors="coerce").dropna()
                    if len(vals) >= 1:
                        unit = {"temperature": "°C", "humidity": "%",
                                "ph": "", "ec": "mS/cm"}.get(col, "")
                        summary_data.append([
                            col,
                            f"{vals.mean():.2f}{unit}",
                            f"{vals.min():.2f}{unit}",
                            f"{vals.max():.2f}{unit}"
                        ])
                st.table(pd.DataFrame(summary_data,
                              columns=["항목", "평균", "최소", "최대"]))

            if "time" in env_df.columns:
                st.subheader("📅 일별 환경 변화 (일별 평균)")

                env_df_time = env_df.copy()
                env_df_time["date"] = env_df_time["time"].dt.date

                date_cols_map = {
                    "temperature": "온도(°C)",
                    "humidity": "습도(%)",
                    "ph": "pH",
                    "ec": "EC(mS/cm)"
                }
                available_metrics = [c for c in ["temperature", "humidity",
                                                 "ph", "ec"] if c in env_df.columns]

                if available_metrics:
                    daily = env_df_time.groupby("date")[available_metrics].mean().reset_index()
                    n_metrics = len(available_metrics)

                    fig_ts = make_subplots(rows=n_metrics, cols=1,
                                           shared_xaxes=True,
                                           subplot_titles=[date_cols_map[m]
                                                           for m in available_metrics])

                    for i, m in enumerate(available_metrics):
                        fig_ts.add_trace(
                            go.Scatter(x=daily["date"], y=daily[m],
                                       mode="lines+markers",
                                       name=date_cols_map[m],
                                       line=dict(width=2)),
                            row=i+1, col=1
                        )
                    fig_ts.update_layout(height=200 * n_metrics, showlegend=False)
                    st.plotly_chart(styled_fig(fig_ts), width="stretch")
                else:
                    st.info("📅 분석할 환경 열(온도·습도·pH·EC)이 없습니다.")

            with st.expander("📄 환경 데이터 원본 보기"):
                st.dataframe(env_df, width="stretch")
                csv_bytes = env_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 환경 데이터 CSV 다운로드",
                    data=csv_bytes,
                    file_name="환경데이터.csv",
                    mime="text/csv"
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ─────────────────────────────────────────────
# Tab 3: 생육 결과
# ─────────────────────────────────────────────
with tab3:
    try:
        st.header("📊 생육 결과 분석")

        if growth_df.empty:
            st.info("📁 생육 결과 CSV 파일을 업로드하면 여기 내용이 표시됩니다.")
        else:
            # 핵심 결과 카드
            if "생중량" in growth_df.columns:
                bio = pd.to_numeric(growth_df["생중량"], errors="coerce").dropna()
                if len(bio) >= 1:
                    mean_val = bio.mean()
                    max_val = bio.max()
                    min_val = bio.min()
                    idx_max = bio.idxmax()
                    idx_min = bio.idxmin()

                    st.subheader("🥇 핵심 결과")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("평균 생중량", f"{mean_val:.1f}g")
                    with c2:
                        st.metric("최대 생중량", f"{max_val:.1f}g",
                                  f"개체번호: {growth_df.loc[idx_max, '개체번호']}")
                    with c3:
                        st.metric("최소 생중량", f"{min_val:.1f}g",
                                  f"개체번호: {growth_df.loc[idx_min, '개체번호']}")

            # 개체별 생육 비교 (막대 그래프)
            st.subheader("📏 개체별 생육 비교 (막대 그래프)")

            bio_qty_cols = [c for c in ["생중량", "잎 수",
                                         "지상부 길이", "지하부 길이"]
                            if c in growth_df.columns]

            if bio_qty_cols:
                col_a, col_b = st.columns(2)

                with col_a:
                    if "생중량" in growth_df.columns:
                        bio_vals = pd.to_numeric(growth_df["생중량"], errors="coerce").dropna()
                        if len(bio_vals) >= 1:
                            q75 = bio_vals.quantile(0.75)
                            q25 = bio_vals.quantile(0.25)
                            labels = growth_df["개체번호"].astype(str).tolist()
                            vals_bar = pd.to_numeric(growth_df["생중량"],
                                                      errors="coerce").tolist()
                            colors = []
                            for v in vals_bar:
                                if pd.notna(v):
                                    if v >= q75:
                                        colors.append("forestgreen")
                                    elif v <= q25:
                                        colors.append("indianred")
                                    else:
                                        colors.append("royalblue")
                                else:
                                    colors.append("lightgray")
                            fig_bar = go.Figure()
                            fig_bar.add_trace(go.Bar(
                                x=labels, y=vals_bar,
                                marker_color=colors,
                                marker_line_color="black",
                                marker_line_width=0.5
                            ))
                            fig_bar.update_layout(
                                title="⭐ 평균 생중량 "
                                      "(초록=상위 25%, 빨강=하위 25%)",
                                xaxis_title="개체번호",
                                yaxis_title="생중량 (g)"
                            )
                            st.plotly_chart(styled_fig(fig_bar), width="stretch")

                with col_b:
                    if "잎 수" in growth_df.columns:
                        leaf_vals = pd.to_numeric(growth_df["잎 수"],
                                                   errors="coerce").dropna()
                        if len(leaf_vals) >= 1:
                            labels = growth_df["개체번호"].astype(str).tolist()
                            vals = pd.to_numeric(growth_df["잎 수"],
                                                  errors="coerce").tolist()
                            fig_leaf = go.Figure()
                            fig_leaf.add_trace(go.Bar(
                                x=labels, y=vals,
                                marker_color="mediumseagreen",
                                marker_line_color="black",
                                marker_line_width=0.5
                            ))
                            fig_leaf.update_layout(
                                title="평균 잎 수",
                                xaxis_title="개체번호",
                                yaxis_title="잎 수 (장)"
                            )
                            st.plotly_chart(styled_fig(fig_leaf), width="stretch")

                col_c, col_d = st.columns(2)

                with col_c:
                    if "지상부 길이" in growth_df.columns:
                        st_len = pd.to_numeric(growth_df["지상부 길이"],
                                                errors="coerce").dropna()
                        if len(st_len) >= 1:
                            labels = growth_df["개체번호"].astype(str).tolist()
                            vals = pd.to_numeric(growth_df["지상부 길이"],
                                                  errors="coerce").tolist()
                            fig_st = go.Figure()
                            fig_st.add_trace(go.Bar(
                                x=labels, y=vals,
                                marker_color="peru",
                                marker_line_color="black",
                                marker_line_width=0.5
                            ))
                            fig_st.update_layout(
                                title="평균 지상부 길이",
                                xaxis_title="개체번호",
                                yaxis_title="지상부 길이 (mm)"
                            )
                            st.plotly_chart(styled_fig(fig_st), width="stretch")

                with col_d:
                    if "지하부 길이" in growth_df.columns:
                        rt_len = pd.to_numeric(growth_df["지하부 길이"],
                                               errors="coerce").dropna()
                        if len(rt_len) >= 1:
                            labels = growth_df["개체번호"].astype(str).tolist()
                            vals = pd.to_numeric(growth_df["지하부 길이"],
                                                  errors="coerce").tolist()
                            fig_rt = go.Figure()
                            fig_rt.add_trace(go.Bar(
                                x=labels, y=vals,
                                marker_color="sienna",
                                marker_line_color="black",
                                marker_line_width=0.5
                            ))
                            fig_rt.update_layout(
                                title="평균 지하부 길이",
                                xaxis_title="개체번호",
                                yaxis_title="지하부 길이 (mm)"
                            )
                            st.plotly_chart(styled_fig(fig_rt), width="stretch")

            # 생중량 분포 (박스플롯)
            if "생중량" in growth_df.columns:
                st.subheader("📦 생중량 분포 (박스플롯)")

                bio_vals = pd.to_numeric(growth_df["생중량"],
                                         errors="coerce").dropna()
                if len(bio_vals) >= 2:
                    fig_box = go.Figure()
                    fig_box.add_trace(go.Box(
                        y=bio_vals,
                        name="생중량",
                        fillcolor="lightblue",
                        line_color="navy",
                        boxpoints="outliers",
                        jitter=0.3,
                        marker=dict(color="darkblue", size=6)
                    ))
                    fig_box.update_layout(
                        title="생중량 분포 (박스플롯)",
                        yaxis_title="생중량 (g)",
                        showlegend=False
                    )
                    st.plotly_chart(styled_fig(fig_box), width="stretch")

                    st.markdown("""
**통계 지표 설명**
- **평균(mean)**: 모든 값을 더해 개수로 나눈 값은 대표적인 중심 값
- **표준편차(std)**: 값들이 평균에서 얼마나 퍼져 있는지 나타내는 산포도
- **변동계수(CV)**: 표준편차를 평균으로 나눈 값, 단위가 다른 그룹 간 비교에 사용
                    """)

                    stats_rows = []
                    stats_rows.append(["평균 (mean)", f"{bio_vals.mean():.2f}g"])
                    stats_rows.append(["표준편차 (std)",
                                       f"{bio_vals.std():.2f}g"])
                    stats_rows.append(["변동계수 (CV)",
                                       f"{(bio_vals.std() / bio_vals.mean() * 100):.1f}%"])
                    stats_rows.append(["최소값", f"{bio_vals.min():.2f}g"])
                    stats_rows.append(["최대값", f"{bio_vals.max():.2f}g"])
                    stats_rows.append(["사분위수 Q1 (하위 25%)",
                                       f"{bio_vals.quantile(0.25):.2f}g"])
                    stats_rows.append(["사분위수 Q3 (상위 25%)",
                                       f"{bio_vals.quantile(0.75):.2f}g"])
                    st.table(pd.DataFrame(stats_rows, columns=["지표", "값"]))

                    # 상위/하위 25% 비교
                    st.subheader("🔬 생중량 상위 25% vs 하위 25% 비교")
                    q75 = bio_vals.quantile(0.75)
                    q25 = bio_vals.quantile(0.25)
                    top_idx = bio_vals[bio_vals >= q75].index
                    low_idx = bio_vals[bio_vals <= q25].index

                    if len(top_idx) >= 1 and len(low_idx) >= 1:
                        c_top, c_low = st.columns(2)

                        with c_top:
                            st.markdown("**🟢 상위 25% 개체**")
                            top_data = growth_df.loc[top_idx,
                                                     ["개체번호", "생중량"]].copy()
                            top_data["생중량"] = pd.to_numeric(
                                top_data["생중량"], errors="coerce")
                            top_data = top_data.sort_values("생중량",
                                                           ascending=False)
                            st.dataframe(top_data, width="stretch")

                        with c_low:
                            st.markdown("**🔴 하위 25% 개체**")
                            low_data = growth_df.loc[low_idx,
                                                      ["개체번호", "생중량"]].copy()
                            low_data["생중량"] = pd.to_numeric(
                                low_data["생중량"], errors="coerce")
                            low_data = low_data.sort_values("생중량",
                                                            ascending=True)
                            st.dataframe(low_data, width="stretch")

            # 상관관계 분석
            st.subheader("🔗 상관관계 분석 (산점도 + 추세선)")

            has_leaf = "잎 수" in growth_df.columns and "생중량" in growth_df.columns
            has_st = "지상부 길이" in growth_df.columns and "생중량" in growth_df.columns

            if has_leaf:
                x = pd.to_numeric(growth_df["잎 수"], errors="coerce")
                y = pd.to_numeric(growth_df["생중량"], errors="coerce")
                fig1 = scatter_with_trend(x, y, "잎 수 (장)", "생중량 (g)",
                                          "잎 수 vs 생중량")
                if fig1:
                    st.plotly_chart(fig1, width="stretch")

            if has_st:
                x = pd.to_numeric(growth_df["지상부 길이"], errors="coerce")
                y = pd.to_numeric(growth_df["생중량"], errors="coerce")
                fig2 = scatter_with_trend(x, y, "지상부 길이 (mm)",
                                          "생중량 (g)",
                                          "지상부 길이 vs 생중량")
                if fig2:
                    st.plotly_chart(fig2, width="stretch")

            if not has_leaf and not has_st:
                st.info("📈 산점도 분석을 위해 '잎 수 vs 생중량' 또는 "
                        "'지상부 길이 vs 생중량' 열이 필요합니다.")

            # 원본 테이블 + 다운로드
            with st.expander("📄 생육 데이터 원본 보기"):
                st.dataframe(growth_df, width="stretch")
                csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 생육 결과 CSV 다운로드",
                    data=csv_bytes,
                    file_name="생육결과데이터.csv",
                    mime="text/csv"
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ─────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────
st.markdown("---")
st.caption("💡 데이터 요약: 평균=대표값, 표준편차=퍼진 정도, "
           "상관계수 r=|1에 가까울수록 강한 관계|, CV=표준편차÷평균")
