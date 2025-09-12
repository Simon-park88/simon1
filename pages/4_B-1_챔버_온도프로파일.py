import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("🌡️ 챔버 온도 프로파일 계산기")
st.info("이 페이지의 계산 결과는 'B_챔버 설정 및 계산' 페이지의 사양을 기반으로 합니다.")


# --- 1. 필요한 모든 데이터와 계산 함수를 이 파일에 직접 정의 ---

# 단열재별 '열전도율(k)' 데이터
K_VALUES = {"우레탄폼": 0.023, "글라스울": 0.040, "세라크울": 0.150}
DENSITY_SUS = 7930  # SUS 비중 (kg/m³)
# 1원 냉동 사이클 COP 테이블
COP_TABLE_1STAGE = {10: 4.0, 0: 3.0, -10: 2.2, -20: 1.5, -25: 1.2}
# 2원 냉동 사이클 COP 테이블
COP_TABLE_2STAGE = {-20: 2.5, -30: 2.0, -40: 1.5, -50: 1.1, -60: 0.8, -70: 0.5}

def calculate_chamber_power(specs):
    """
    주어진 사양(specs)으로 '온도 변화 시'와 '온도 유지 시'의 
    챔버 전체 소비 전력(kW)을 계산하여 딕셔너리로 반환하는 함수.
    """
    try:
        # --- 사양 추출 (값이 없을 경우 기본값 사용) ---
        chamber_w = specs.get('chamber_w', 1000); chamber_d = specs.get('chamber_d', 1000); chamber_h = specs.get('chamber_h', 1000)
        insulation_type = specs.get('insulation_type', '우레탄폼'); insulation_thickness = specs.get('insulation_thickness', 100)
        target_temp = specs.get('target_temp', 25.0); outside_temp = specs.get('outside_temp', 25.0)
        load_type = specs.get('load_type', '없음'); num_cells = specs.get('num_cells', 0)
        fan_motor_load = specs.get('fan_motor_load', 0.75); fan_soak_factor = specs.get('fan_soak_factor', 30) / 100.0
        sus_thickness = specs.get('sus_thickness', 1.2); ramp_rate = specs.get('ramp_rate', 1.0)
        refrigeration_system = specs.get('refrigeration_system', '1원 냉동')
        min_temp_spec = specs.get('min_temp_spec', -40.0)
        safety_factor = specs.get('safety_factor', 1.5)

        # --- 모든 부하 계산 ---
        k_value = K_VALUES.get(insulation_type, 0.023)
        thickness_m = insulation_thickness / 1000.0
        U_value = (k_value / thickness_m) if thickness_m > 0 else 0
        A = 2 * ((chamber_w * chamber_d) + (chamber_w * chamber_h) + (chamber_d * chamber_h)) / 1_000_000
        delta_T = abs(target_temp - outside_temp)
        conduction_load_w = U_value * A * delta_T

        sus_volume_m3 = A * (sus_thickness / 1000.0)
        calculated_internal_mass = sus_volume_m3 * DENSITY_SUS
        
        volume_m3 = (chamber_w * chamber_d * chamber_h) / 1_000_000_000
        ramp_rate_c_per_sec = ramp_rate / 60.0
        air_load_w = (volume_m3 * 1.225) * 1005 * ramp_rate_c_per_sec
        internal_mass_load_w = calculated_internal_mass * 500 * ramp_rate_c_per_sec
        ramp_load_w = air_load_w + internal_mass_load_w

        internal_product_load_w = num_cells * 50.0 if load_type == '각형 배터리' else 0.0
        fan_motor_load_w_ramp = fan_motor_load * 1000
        fan_motor_load_w_soak = fan_motor_load_w_ramp * fan_soak_factor

        total_heat_load_ramp = conduction_load_w + ramp_load_w + internal_product_load_w + fan_motor_load_w_ramp
        total_heat_load_soak = conduction_load_w + internal_product_load_w + fan_motor_load_w_soak

        # --- 최종 소비 전력 예측 ---
        if target_temp > -25:
            operating_system = "1원 냉동 (작동 중)"; sorted_cop_items = sorted(COP_TABLE_1STAGE.items())
        else:
            operating_system = "2원 냉동 (작동 중)"; sorted_cop_items = sorted(COP_TABLE_2STAGE.items())
        
        cop_temps = np.array([item[0] for item in sorted_cop_items])
        cop_values = np.array([item[1] for item in sorted_cop_items])
        cop = np.interp(target_temp, cop_temps, cop_values)

        required_electrical_power_ramp = total_heat_load_ramp / cop if cop > 0 else float('inf')
        required_hp_ramp = (required_electrical_power_ramp * safety_factor) / 746
        required_electrical_power_soak = total_heat_load_soak / cop if cop > 0 else float('inf')
        required_hp_soak = (required_electrical_power_soak * safety_factor) / 746

        actual_hp, actual_rated_power = 0, 0
        if refrigeration_system == '1원 냉동':
            actual_hp = specs.get('actual_hp_1stage', 5.0)
            actual_rated_power = specs.get('actual_rated_power_1stage', 3.5)
        elif refrigeration_system == '2원 냉동':
            if operating_system == "1원 냉동 (작동 중)":
                actual_hp = specs.get('actual_hp_2stage_h', 3.0)
                actual_rated_power = specs.get('actual_rated_power_2stage_h', 2.0)
            else:
                actual_hp = specs.get('actual_hp_2stage_h', 3.0) + specs.get('actual_hp_2stage_l', 2.0)
                actual_rated_power = specs.get('actual_rated_power_2stage_h', 2.0) + specs.get('actual_rated_power_2stage_l', 1.5)

        load_factor_ramp = required_hp_ramp / actual_hp if actual_hp > 0 else 0
        estimated_power_ramp_kw = actual_rated_power * load_factor_ramp
        load_factor_soak = required_hp_soak / actual_hp if actual_hp > 0 else 0
        estimated_power_soak_kw = actual_rated_power * load_factor_soak
        
        # 챔버 전체 최종 소비 전력 = 냉동기 + 팬/모터
        total_consumption_ramp = estimated_power_ramp_kw + fan_motor_load
        total_consumption_soak = estimated_power_soak_kw + (fan_motor_load * fan_soak_factor)
        
        return {"power_ramp_kw": total_consumption_ramp, "power_soak_kw": total_consumption_soak}

    except Exception:
        # st.session_state에 접근할 수 없으므로, 에러를 직접 반환하거나 로깅할 수 있습니다.
        return {"power_ramp_kw": 0, "power_soak_kw": 0}


# --- 2. st.session_state 초기화 ---
if 'profile_df' not in st.session_state:
    st.session_state.profile_df = pd.DataFrame(
        [{"목표 온도 (°C)": 25.0, "유지 시간 (H)": 1.0}],
        columns=["목표 온도 (°C)", "유지 시간 (H)"]
    )
if 'initial_temp' not in st.session_state:
    st.session_state.initial_temp = 25.0

# --- 3. 온도 프로파일 입력 UI ---
st.subheader("초기 조건 설정")
st.number_input("초기 챔버 실내 온도 (°C)", key='initial_temp')

st.subheader("온도 프로파일 구성 테이블")

if st.button("➕ 스텝 추가"):
    new_step = pd.DataFrame([{"목표 온도 (°C)": 25.0, "유지 시간 (H)": 1.0}])
    st.session_state.profile_df = pd.concat([st.session_state.profile_df, new_step], ignore_index=True)
    st.rerun()

st.session_state.profile_df['목표 온도 (°C)'] = st.session_state.profile_df['목표 온도 (°C)'].fillna(25.0)

edited_df = st.data_editor(
    st.session_state.profile_df,
    column_config={
        "목표 온도 (°C)": st.column_config.NumberColumn("목표 온도 (°C)", format="%.1f", required=True),
        "유지 시간 (H)": st.column_config.NumberColumn("유지 시간 (H)", help="'Soak' 상태일 때의 유지 시간을 입력합니다.", format="%.2f"),
    },
    num_rows="dynamic",
    hide_index=True
)
st.session_state.profile_df = edited_df

# --- 4. 자동 계산 로직 ---
if st.button("⚙️ 프로파일 계산 실행"):

    # 'chamber_specs'가 st.session_state에 있는지 안전하게 확인하고 가져옵니다.
    if "chamber_specs" not in st.session_state or not st.session_state["chamber_specs"]:
        st.warning("⚠️ 먼저 'B_챔버 설정 및 계산' 페이지에서 챔버 사양을 저장해주세요.")
        st.stop() 

    try:
        # 저장된 'chamber_specs' 딕셔너리만 정확히 가져옵니다.
        chamber_specs_original = st.session_state["chamber_specs"].copy()
        
        # 계산에 사용될 핵심 사양 값을 여기서 직접 확인합니다.
        st.subheader("⚙️ 계산에 사용된 사양 (확인용)")
        st.json({
            "온도 변화 시 팬/모터 부하 (kW)": chamber_specs_original.get('fan_motor_load'),
            "온도 유지 시 팬/모터 부하율 (%)": chamber_specs_original.get('fan_soak_factor'),
            "설정된 냉동 방식": chamber_specs_original.get('refrigeration_system'),
            "온도 변화 속도 (°C/min)": chamber_specs_original.get('ramp_rate')
        })
        # ------------------------------------

        results = []
        total_time = 0.0
        total_kwh = 0.0
        current_temp = st.session_state.initial_temp
        
        
        # 사용자가 입력한 프로파일 테이블을 순회하며 계산
        for index, row in edited_df.iterrows(): # st.session_state.profile_df 대신 edited_df 사용
            target_temp_step = row['목표 온도 (°C)']
            soak_time = row['유지 시간 (H)']
            
            if pd.isna(target_temp_step):
                continue # 목표 온도가 비어있으면 해당 스텝은 건너뜁니다.
            
            # 현재 스텝의 목표 온도를 반영하여 소비 전력 다시 계산
            # 복사본 딕셔너리의 목표 온도를 업데이트하여 계산 함수에 전달
            specs_for_step = chamber_specs_original.copy()
            specs_for_step['target_temp'] = target_temp_step

            power_values = calculate_chamber_power(specs_for_step)
            power_ramp_kw = power_values['power_ramp_kw']
            power_soak_kw = power_values['power_soak_kw']
            
            # Ramp 구간 자동 계산
            if target_temp_step != current_temp:
                ramp_rate = chamber_specs_original.get('ramp_rate', 1.0)
                delta_t = abs(target_temp_step - current_temp)
                ramp_time = (delta_t / ramp_rate) / 60.0 if ramp_rate > 0 else 0
                ramp_kwh = power_ramp_kw * ramp_time
                total_time += ramp_time
                total_kwh += ramp_kwh
                results.append([f"{index + 1}-Ramp", f"{current_temp:.1f} → {target_temp_step:.1f}", f"{ramp_time:.2f}", f"{ramp_kwh:.2f}"])
                current_temp = target_temp_step

            # Soak 구간 계산
            if pd.notna(soak_time) and soak_time > 0:
                soak_kwh = power_soak_kw * soak_time
                total_time += soak_time
                total_kwh += soak_kwh
                results.append([f"{index + 1}-Soak", f"{current_temp:.1f} 유지", f"{soak_time:.2f}", f"{soak_kwh:.2f}"])
                
        # 최종 결과를 session_state에 저장
        st.session_state.chamber_profile_kwh = total_kwh
        st.session_state.chamber_profile_time = total_time
        st.session_state.profile_results = results
        st.success("프로파일 계산이 완료되었습니다!")

    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")
        st.exception(e)

# --- 5. 결과 표시 ---
st.markdown("---")
st.subheader("프로파일 계산 결과")

if 'profile_results' in st.session_state:
    results = st.session_state.profile_results
    if results:
        result_df = pd.DataFrame(results, columns=["구간", "내용", "소요 시간(H)", "소비 전력량(kWh)"])
        st.dataframe(result_df)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("프로파일 총 소요 시간 (H)", f"{st.session_state.get('chamber_profile_time', 0):.2f}")
    with col2:
        st.metric("챔버 총 소비 전력량 (kWh)", f"{st.session_state.get('chamber_profile_kwh', 0):.2f}")