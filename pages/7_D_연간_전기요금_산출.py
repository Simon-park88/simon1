import streamlit as st
import pandas as pd
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("💰 연간 전기 요금 산출")
st.info("각 설비의 연간 운영 계획을 종합하고, '프로필'로 저장하여 최종 전기 요금을 정밀하게 예측합니다.")

# --- 1. st.session_state 및 헬퍼 함수 ---
def initialize_state():
    """세션 상태 초기화"""
    # 데이터 저장용
    if 'cycler_plan_df' not in st.session_state:
        st.session_state.cycler_plan_df = pd.DataFrame(columns=["저장된 레시피", "반복 유형", "계획 시간 (H)"])
    if 'saved_profiles' not in st.session_state:
        st.session_state.saved_profiles = {}
    if 'current_summary' not in st.session_state:
        st.session_state.current_summary = None
    if 'final_calc_results' not in st.session_state:
        st.session_state.final_calc_results = None
        
    # UI 입력값 유지용
    if 'rate_peak_kw' not in st.session_state: st.session_state.rate_peak_kw = 9810.0
    if 'rate_kwh' not in st.session_state: st.session_state.rate_kwh = 147.8
    
    if 'chamber_op_mode' not in st.session_state: st.session_state.chamber_op_mode = "수동 계획 입력"
    if 'chamber_profile_select' not in st.session_state: st.session_state.chamber_profile_select = "선택 안함"
    if 'chamber_spec_select' not in st.session_state: st.session_state.chamber_spec_select = "선택 안함"
    if 'chamber_qty' not in st.session_state: st.session_state.chamber_qty = 1
    if 'chamber_cycles_per_day' not in st.session_state: st.session_state.chamber_cycles_per_day = 1
    if 'chamber_soak_hours_per_day' not in st.session_state: st.session_state.chamber_soak_hours_per_day = 8.0
    if 'chamber_operating_days' not in st.session_state: st.session_state.chamber_operating_days = 365
    
    if 'chiller_spec_select' not in st.session_state: st.session_state.chiller_spec_select = "선택 안함"

initialize_state()

def calculate_all_power(cycler_plan_df, 
                        chamber_op_mode, chamber_spec_name, chamber_quantity, chamber_profile_name,
                        chiller_spec_name):
    """모든 설비의 전력 정보를 계산하는 중앙 함수"""
    results = {}
    plan_is_valid = True

    # --- 1. 충방전기 계산 ---
    cycler_annual_kwh, cycler_peak_kw = 0.0, 0.0
    plan_total_kwh = 0.0
    plan_total_hours = cycler_plan_df["계획 시간 (H)"].sum()

    if plan_total_hours > 8760:
        st.error(f"충방전기 총 계획 시간({plan_total_hours:,.1f} H)이 1년(8760 H)을 초과합니다.")
        plan_is_valid = False
    
    if not cycler_plan_df.empty and plan_is_valid:
        all_demand_peaks_in_plan = [0]
        for _, row in cycler_plan_df.iterrows():
            recipe_name = row["저장된 레시피"] 
            if recipe_name not in saved_cycler_recipes or recipe_name == "선택하세요": continue
            
            spec = saved_cycler_recipes[recipe_name]
            all_demand_peaks_in_plan.append(spec.get('demand_peak_power', 0.0))
            
            kwh_per_run = spec.get('total_kwh', 0.0)
            hours_per_run = spec.get('total_hours', 1.0)
            if hours_per_run <= 0: hours_per_run = 1.0
            
            planned_hours = row["계획 시간 (H)"]
            num_runs_in_plan = planned_hours / hours_per_run
            plan_total_kwh += kwh_per_run * num_runs_in_plan
        
        cycler_peak_kw = max(all_demand_peaks_in_plan)

        if plan_total_hours > 0:
            annual_repetition_factor = 8760 / plan_total_hours
            cycler_annual_kwh = plan_total_kwh * annual_repetition_factor
        else:
            cycler_annual_kwh = 0
    
    results['cycler'] = {'peak': cycler_peak_kw, 'kwh': cycler_annual_kwh}

    # --- 2. 챔버 계산 ---
    chamber_annual_kwh, chamber_peak_kw = 0.0, 0.0

    if chamber_op_mode == "수동 계획 입력":
        if chamber_spec_name != "선택 안함" and chamber_quantity > 0 and chamber_spec_name in saved_chamber_specs:
            spec = saved_chamber_specs[chamber_spec_name]
            ramp_kw = spec.get('total_consumption_ramp_kw', 0.0)
            soak_kw = spec.get('total_consumption_soak_kw', 0.0)
            
            delta_t = abs(spec.get('min_temp_spec', 25) - spec.get('outside_temp', 25))
            ramp_rate_min = spec.get('ramp_rate', 1.0)
            ramp_time_h_per_cycle = (delta_t / ramp_rate_min) / 60.0 if ramp_rate_min > 0 else 0
            
            annual_ramp_hours = ramp_time_h_per_cycle * st.session_state.chamber_cycles_per_day * st.session_state.chamber_operating_days
            annual_soak_hours = st.session_state.chamber_soak_hours_per_day * st.session_state.chamber_operating_days
            
            chamber_annual_kwh = ((ramp_kw * annual_ramp_hours) + (soak_kw * annual_soak_hours)) * chamber_quantity
            
            peak_per_chamber = 0
            if annual_ramp_hours > 0:
                peak_per_chamber = ramp_kw
            elif annual_soak_hours > 0:
                peak_per_chamber = soak_kw
            chamber_peak_kw = peak_per_chamber * chamber_quantity

    elif chamber_op_mode == "저장된 프로파일 불러오기":
        if chamber_profile_name != "선택 안함" and chamber_profile_name in saved_chamber_profiles:
            profile_data = saved_chamber_profiles[chamber_profile_name]
            profile_kwh = profile_data.get('total_profile_kwh', 0)
            profile_hours = profile_data.get('total_profile_hours', 1)
            chamber_peak_kw = profile_data.get('peak_power_kw', 0)
            
            if profile_hours > 0:
                annual_repetition_factor = 8760 / profile_hours
                chamber_annual_kwh = profile_kwh * annual_repetition_factor
            else:
                chamber_annual_kwh = 0

    results['chamber'] = {'peak': chamber_peak_kw, 'kwh': chamber_annual_kwh}

    # --- 3. 칠러 계산 ---
    chiller_annual_kwh, chiller_peak_kw = 0.0, 0.0
    if chiller_spec_name != "선택 안함" and chiller_spec_name in saved_chiller_calcs:
        spec = saved_chiller_calcs[chiller_spec_name]
        chiller_peak_kw = spec.get('peak_chiller_power', 0.0)
        chiller_annual_kwh = spec.get('annual_kwh', 0.0)
    
    results['chiller'] = {'peak': chiller_peak_kw, 'kwh': chiller_annual_kwh}
    
    # --- 최종 합계 ---
    total_peak_kw = results['cycler']['peak'] + results['chamber']['peak'] + results['chiller']['peak']
    total_annual_kwh = results['cycler']['kwh'] + results['chamber']['kwh'] + results['chiller']['kwh']
    results['total'] = {'peak': total_peak_kw, 'kwh': total_annual_kwh}
    
    return results if plan_is_valid else None

# ★★★★★ 추가: 프로파일 삭제 콜백 함수 ★★★★★
def delete_summary_profile_callback(profile_name):
    """'저장된 프로필 관리'에서 선택된 프로필을 삭제하는 콜백 함수"""
    if profile_name in st.session_state.saved_profiles:
        del st.session_state.saved_profiles[profile_name]
        st.success(f"'{profile_name}' 프로필을 삭제했습니다.")
    else:
        st.warning("삭제할 프로필을 찾을 수 없습니다.")


# --- 2. 데이터 불러오기 ---
saved_cycler_recipes = st.session_state.get('saved_recipes', {})
saved_chamber_specs = st.session_state.get('saved_chamber_specs', {})
saved_chiller_calcs = st.session_state.get('saved_chiller_calcs', {})
saved_chamber_profiles = st.session_state.get('saved_chamber_profiles', {})

# --- 3. UI 구성: 설비별 운영 계획 ---
st.subheader("1. 충방전기 연간 운영 계획 설정")
st.caption("아래 표에 여러 레시피를 순차적으로 추가하여 1년간의 운영 시나리오를 구성합니다. 이 계획 전체가 1년(8760시간)동안 반복된다고 가정하고 계산합니다.")
edited_df = st.data_editor(
    st.session_state.cycler_plan_df,
    column_config={
        "저장된 레시피": st.column_config.SelectboxColumn("저장된 레시피", options=["선택하세요"] + list(saved_cycler_recipes.keys()), required=True),
        "반복 유형": st.column_config.SelectboxColumn("반복 유형", options=["1회", "반복"], required=True),
        "계획 시간 (H)": st.column_config.NumberColumn("계획 시간 (H)", help="'1회'는 자동 계산되며, '반복'은 이 테스트에 할당할 연간 총 시간을 직접 입력합니다.")
    },
    num_rows="dynamic", key="cycler_plan_editor", hide_index=True
)
for i, row in edited_df.iterrows():
    recipe_name = row["저장된 레시피"]
    if row["반복 유형"] == "1회" and recipe_name in saved_cycler_recipes:
        hours_per_run = saved_cycler_recipes[recipe_name].get('total_hours', 0)
        edited_df.at[i, "계획 시간 (H)"] = hours_per_run
st.session_state.cycler_plan_df = edited_df.reset_index(drop=True)

st.markdown("---")
st.subheader("2. 챔버 및 칠러 연간 운영 계획")

col_chamber, col_chiller = st.columns(2)
with col_chamber:
    st.markdown("##### 🔌 챔버")
    st.radio("운영 방식 선택", ["수동 계획 입력", "저장된 프로파일 불러오기"], key="chamber_op_mode", horizontal=True)
    
    if st.session_state.chamber_op_mode == "수동 계획 입력":
        st.selectbox("적용할 챔버 사양", options=["선택 안함"] + list(saved_chamber_specs.keys()), key="chamber_spec_select")
        st.number_input("챔버 수량", min_value=0, key="chamber_qty")
        st.number_input("하루 당 사이클(Ramp) 횟수", min_value=0, key='chamber_cycles_per_day', help="이 값이 0이면 Ramp 운전은 없고 Soak 운전만 수행하는 것으로 간주합니다.")
        st.number_input("하루 평균 유지(Soak) 시간 (H)", min_value=0.0, step=0.5, format="%.1f", key='chamber_soak_hours_per_day')
        st.number_input("연간 가동 일수", min_value=0, max_value=365, key='chamber_operating_days')
    else: # 저장된 프로파일 불러오기
        st.selectbox("적용할 챔버 운영 프로파일", options=["선택 안함"] + list(saved_chamber_profiles.keys()), key="chamber_profile_select")
        profile_name = st.session_state.chamber_profile_select
        if profile_name != "선택 안함" and profile_name in saved_chamber_profiles:
            profile_data = saved_chamber_profiles[profile_name]
            st.info(f"""
            **선택된 프로파일 정보:**
            - **기반 챔버 사양:** {profile_data.get('source_chamber_spec')}
            - **챔버 수량:** {profile_data.get('chamber_count')} 대
            - **1회 프로파일 시간:** {profile_data.get('total_profile_hours'):.2f} H
            - **1회 프로파일 전력량:** {profile_data.get('total_profile_kwh'):.2f} kWh
            - **Peak 전력:** {profile_data.get('peak_power_kw'):.2f} kW
            """)

with col_chiller:
    st.markdown("##### 💧 칠러")
    st.selectbox("적용할 칠러 계산 결과를 선택하세요", 
                 options=["선택 안함"] + list(saved_chiller_calcs.keys()), 
                 key="chiller_spec_select",
                 help="'칠러 용량 산정' 페이지에서 저장된 계산 결과를 불러옵니다.")
    
    chiller_name = st.session_state.chiller_spec_select
    if chiller_name != "선택 안함" and chiller_name in saved_chiller_calcs:
        chiller_data = saved_chiller_calcs[chiller_name]
        st.info(f"""
        **선택된 칠러 정보:**
        - **Peak 전력:** {chiller_data.get('peak_chiller_power', 0):.2f} kW
        - **연간 전력량:** {chiller_data.get('annual_kwh', 0):,.0f} kWh
        """)

st.markdown("---")

# --- 4. 전력 정보 종합 및 저장 ---
st.subheader("3. 계산된 전력 정보 종합")
if st.button("현재 설정값으로 전력 정보 계산 및 불러오기", type="primary"):
    summary = calculate_all_power(
        st.session_state.cycler_plan_df,
        st.session_state.chamber_op_mode,
        st.session_state.chamber_spec_select,
        st.session_state.chamber_qty,
        st.session_state.chamber_profile_select,
        st.session_state.chiller_spec_select
    )
    if summary:
        st.session_state.current_summary = summary

if st.session_state.current_summary:
    summary = st.session_state.current_summary
    summary_df = pd.DataFrame({
        "Peak 전력 (kW)": [
            summary['cycler']['peak'],
            summary['chamber']['peak'],
            summary['chiller']['peak'],
            summary['total']['peak']
        ],
        "연간 전력량 (kWh)": [
            summary['cycler']['kwh'],
            summary['chamber']['kwh'],
            summary['chiller']['kwh'],
            summary['total']['kwh']
        ]
    }, index=["충방전기", "챔버", "칠러", "합계"])
    
    st.dataframe(summary_df.style.format("{:,.2f}").apply(lambda x: ['font-weight: bold' if x.name == "합계" else '' for i in x], axis=1))

    with st.form("save_profile_form"):
        profile_name = st.text_input("저장할 프로필 이름", placeholder="예: 25년도 A라인 증설 계획")
        submitted = st.form_submit_button("현재 종합 정보 저장")
        if submitted:
            if not profile_name:
                st.warning("프로필 이름을 입력해주세요.")
            elif profile_name == "현재 계산된 값 사용":
                st.error("'현재 계산된 값 사용'은 예약된 이름으로 프로필을 저장할 수 없습니다.")
            elif profile_name in st.session_state.saved_profiles:
                st.warning(f"'{profile_name}' 이름의 프로필이 이미 존재합니다. 덮어쓰려면 먼저 삭제해주세요.")
            else:
                st.session_state.saved_profiles[profile_name] = summary['total']
                st.success(f"'{profile_name}' 프로필이 저장되었습니다.")
    
    # ★★★★★ 수정된 부분: 저장된 프로필 관리 UI 및 삭제 로직 ★★★★★
    if st.session_state.saved_profiles:
        st.markdown("---")
        st.write("##### 💾 저장된 프로필 관리")
        
        for name in list(st.session_state.saved_profiles.keys()):
            col1, col2 = st.columns([4, 1])
            profile_data = st.session_state.saved_profiles[name]
            with col1:
                st.info(f"**{name}**: Peak {profile_data.get('peak', 0):.2f} kW, 연간 전력량 {profile_data.get('kwh', 0):,.0f} kWh")
            with col2:
                # 각 버튼에 고유한 key를 부여하고, on_click에 콜백 함수와 인자를 전달
                st.button("삭제", key=f"delete_{name}", on_click=delete_summary_profile_callback, args=(name,))

st.markdown("---")

st.subheader("4. 연간 전기 요금 계산 실행")
col_rate1, col_rate2 = st.columns(2)
with col_rate1: st.number_input("기본요금 단가 (원/kW)", key='rate_peak_kw', format="%.1f")
with col_rate2: st.number_input("전력량요금 단가 (원/kWh)", key='rate_kwh', format="%.1f")

profile_options = ["현재 계산된 값 사용"] + list(st.session_state.saved_profiles.keys())
selected_profiles = st.multiselect(
    "계산에 적용할 프로필 선택 (다중 선택 가능)",
    options=profile_options,
    help="여러 프로필을 선택하면 Peak 전력과 연간 전력량이 합산되어 계산됩니다."
)

if st.button("📈 **연간 전기 요금 계산**"):
    if not selected_profiles:
        st.error("계산할 프로필을 하나 이상 선택해주세요.")
    else:
        combined_peak = 0.0
        combined_kwh = 0.0
        calculation_valid = True
        
        for profile_name in selected_profiles:
            data_to_add = None
            if profile_name == "현재 계산된 값 사용":
                if st.session_state.current_summary:
                    data_to_add = st.session_state.current_summary['total']
                else:
                    st.warning("'현재 계산된 값 사용'을 선택했지만, 먼저 전력 정보 계산을 실행해야 합니다. 해당 항목은 합산에서 제외됩니다.")
                    calculation_valid = False
                    continue 
            elif profile_name in st.session_state.saved_profiles:
                data_to_add = st.session_state.saved_profiles[profile_name]

            if data_to_add:
                combined_peak += data_to_add.get('peak', 0.0)
                combined_kwh += data_to_add.get('kwh', 0.0)

        if combined_peak > 0 or combined_kwh > 0:
            st.session_state.final_calc_results = {
                'peak': combined_peak,
                'kwh': combined_kwh
            }
        elif calculation_valid:
            st.session_state.final_calc_results = None

if st.session_state.final_calc_results:
    results = st.session_state.final_calc_results
    st.markdown("---"); st.subheader("✅ 최종 계산 결과")
    
    total_peak = results.get('peak', 0.0)
    total_kwh = results.get('kwh', 0.0)
    
    col_total1, col_total2 = st.columns(2)
    with col_total1:
        st.metric("⚡️ 적용 Peak 전력", f"{total_peak:,.2f} kW", help="선택된 프로필들의 합산 Peak 전력입니다.")
    with col_total2:
        st.metric("💡 적용 연간 총 전력량", f"{total_kwh:,.0f} kWh", help="선택된 프로필들의 합산 전력량입니다.")
        
    base_fee = total_peak * st.session_state.rate_peak_kw * 12
    usage_fee = total_kwh * st.session_state.rate_kwh
    subtotal = base_fee + usage_fee
    vat = subtotal * 0.1
    power_fund = math.floor((subtotal * 0.037) / 10) * 10 
    total_fee = subtotal + vat + power_fund
    
    st.success(f"**연간 총 예상 전기 요금: 약 {total_fee:,.0f} 원**")
    
    st.markdown(f"""
    <div style="background-color:#f0f2f6; padding: 15px; border-radius: 10px;">
    
    - **기본요금 (연간):** `{total_peak:,.2f} kW × {st.session_state.rate_peak_kw:,.1f} 원/kW × 12개월 =` **`{base_fee:,.0f} 원`**
    - **전력량요금 (연간):** `{total_kwh:,.0f} kWh × {st.session_state.rate_kwh:.1f} 원/kWh =` **`{usage_fee:,.0f} 원`**
    - **전기요금계 (기본+전력량):** `{subtotal:,.0f} 원`
    - **부가가치세 (10%):** `{vat:,.0f} 원`
    - **전력산업기반기금 (3.7%):** `{power_fund:,.0f} 원`
    
    </div>
    """, unsafe_allow_html=True)

