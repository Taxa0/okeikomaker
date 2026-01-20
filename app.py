import streamlit as st
import pandas as pd
import pulp

# ページ設定
st.set_page_config(page_title="部活シフト作成アプリ", layout="wide")

# --- CSS設定 ---
st.markdown("""
<style>
    /* 全体の余白 */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    div[data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    div[data-testid="column"] { padding: 0px !important; }

    /* --- ボタン共通スタイル --- */
    .stButton { margin: 0px !important; padding: 0px !important; }
    
    /* ボタン本体 */
    .stButton button {
        height: 34px !important;
        min-height: 34px !important;
        padding: 0px 4px !important;
        font-weight: bold !important;
        font-size: 13px !important;
        border-radius: 4px !important;
        line-height: 1 !important;
    }
    .stButton button div[data-testid="stMarkdownContainer"] p {
        width: 100%; text-align: center; margin: 0px;
    }

    /* Primaryボタン（緑色）: 移動・交換などのアクション可能状態 */
    div.stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
        color: white !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838 !important;
    }

    /* Disabledボタン（赤色）: 編集中（選択済み）の状態 */
    div.stButton > button:disabled {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: white !important;
        opacity: 1.0 !important;
        cursor: default !important;
    }
    div.stButton > button:disabled p {
        color: white !important;
    }

    /* --- 日程ラベル (移動不可の場合: 紺色) --- */
    .date-label {
        display: flex; align-items: center; justify-content: center;
        width: 100%; height: 34px;
        background-color: #2c3e50; color: white;
        border-radius: 4px; font-size: 13px; font-weight: bold;
        margin-bottom: 2px; box-sizing: border-box;
    }

    /* --- ロックされた部員 (グレー) --- */
    .locked-member {
        display: flex; align-items: center; justify-content: center;
        width: 100%; height: 34px;
        background-color: #e9ecef; color: #adb5bd;
        border: 1px solid rgba(49, 51, 63, 0.2);
        border-radius: 4px; font-size: 13px; font-weight: bold;
        margin-bottom: 2px; white-space: nowrap; overflow: hidden;
        box-sizing: border-box; cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)

# --- 関数定義 ---

def solve_shift_schedule(df, min_list, max_list):
    """数理最適化を用いてシフトを作成する関数"""
    dates = df.iloc[:, 0].fillna("").astype(str).str.strip().tolist()
    members = df.columns[1:].tolist()
    
    if len(dates) != len(min_list) or len(dates) != len(max_list):
        return None, False

    prob = pulp.LpProblem("Shift_Scheduler", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("assign", ((d, m) for d in range(len(dates)) for m in range(len(members))), cat='Binary')

    preference_scores = {}
    for d_idx, date in enumerate(dates):
        for m_idx, member in enumerate(members):
            val = df.iloc[d_idx, m_idx + 1]
            status = str(val).strip() if pd.notna(val) else "-"
            score = 0
            if status == "○": score = 2
            elif status == "△": score = 1
            else: prob += x[d_idx, m_idx] == 0
            preference_scores[(d_idx, m_idx)] = score

    prob += pulp.lpSum([x[d, m] * preference_scores[(d, m)] for d in range(len(dates)) for m in range(len(members))])
    for m in range(len(members)): prob += pulp.lpSum([x[d, m] for d in range(len(dates))]) <= 1
    
    for d in range(len(dates)):
        total_assigned = pulp.lpSum([x[d, m] for m in range(len(members))])
        val_min = int(min_list[d]) if pd.notna(min_list[d]) else 0
        val_max = int(max_list[d]) if pd.notna(max_list[d]) else 1
        prob += total_assigned >= val_min
        prob += total_assigned <= val_max

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] == "Optimal":
        results = []
        for d in range(len(dates)):
            assigned = [members[m] for m in range(len(members)) if pulp.value(x[d, m]) == 1]
            assigned.sort()
            results.append({"日程": dates[d], "担当者": ", ".join(assigned), "人数": len(assigned)})
        return pd.DataFrame(results), True
    return None, False

def get_status(df, date_val, member_name):
    row = df[df.iloc[:, 0].astype(str).str.strip() == date_val]
    if row.empty: return "-"
    val = row.iloc[0][member_name]
    return str(val).strip() if pd.notna(val) else "-"

def can_member_move(df, current_date, member_name):
    dates_col = df.iloc[:, 0].astype(str).str.strip()
    status_col = df[member_name].astype(str).str.strip()
    movable_days = df[(dates_col != current_date) & (status_col.isin(['○', '△']))]
    return not movable_days.empty

# --- UI部分 ---
st.title("部活シフト作成")

if 'shift_result' not in st.session_state: st.session_state.shift_result = None
if 'editing_member' not in st.session_state: st.session_state.editing_member = None 
if 'editing_date' not in st.session_state: st.session_state.editing_date = None

uploaded_file = st.file_uploader("CSVファイル", type=['csv'], label_visibility="collapsed")

if uploaded_file is not None:
    try:
        try: raw_df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            raw_df = pd.read_csv(uploaded_file, encoding='cp932')

        # 【修正】不要な行（最終更新日時、コメント）の削除ロジック
        # 1列目の値を文字列化し、「最終更新日時」や「コメント」で始まる行を除外する
        if len(raw_df) > 0:
            # 1列目のデータを取得（欠損値は空文字にする）
            first_col = raw_df.iloc[:, 0].astype(str).fillna("")
            # 除外キーワード
            ignore_keywords = ['最終更新日時', 'コメント']
            # キーワードで始まらない行だけを残すフィルタ
            mask = ~first_col.apply(lambda x: any(x.startswith(k) for k in ignore_keywords))
            clean_df = raw_df[mask].reset_index(drop=True)
        else:
            clean_df = raw_df
        
        # 列名の修正
        if len(clean_df.columns) > 0 and "Unnamed" in str(clean_df.columns[0]):
            clean_df.rename(columns={clean_df.columns[0]: '日程'}, inplace=True)

        if len(clean_df.columns) < 2:
             st.error("データ形式エラー")
        else:
            members_list = clean_df.columns[1:].tolist()
            dates_list = clean_df.iloc[:, 0].fillna("").astype(str).str.strip().tolist()
            total_members = int(len(members_list))
            total_days = int(len(dates_list))
            
            # 出席可能者のカウント
            attendees = []
            for m in members_list:
                s_series = clean_df[m].astype(str).str.strip()
                if any(s in ['○', '△'] for s in s_series): attendees.append(m)
            num_attendees = len(attendees)

            # --- 計算ロジック: デフォルト値の算出 (出席可能者数ベース) ---
            if total_days > 0 and num_attendees > 0:
                default_bulk_max = (num_attendees // total_days) + 1
                default_bulk_min = max(0, default_bulk_max - 2)
            else:
                default_bulk_max = 1
                default_bulk_min = 0
            
            safe_input_max = total_members if total_members > 0 else 1
            default_bulk_max = min(default_bulk_max, safe_input_max)
            default_bulk_min = min(default_bulk_min, safe_input_max)

            st.markdown("### 人数設定")
            st.info(f"出席可能者: **{num_attendees} / {total_members} 名** (全{total_days}日程)")
            
            if 'last_filename' not in st.session_state or st.session_state.last_filename != uploaded_file.name:
                st.session_state.last_filename = uploaded_file.name
                st.session_state.settings_df = pd.DataFrame({
                    "日程": dates_list, 
                    "最小人数": [default_bulk_min] * len(dates_list), 
                    "最大人数": [default_bulk_max] * len(dates_list)
                })

            col1, col2, col3 = st.columns([1,1,1])
            with col1: b_min = st.number_input("一括最小", 0, safe_input_max, default_bulk_min)
            with col2: b_max = st.number_input("一括最大", 1, safe_input_max, default_bulk_max)
            with col3:
                st.write("") 
                st.write("")
                if st.button("全日程に適用"):
                    st.session_state.settings_df["最小人数"] = b_min
                    st.session_state.settings_df["最大人数"] = b_max
                    st.rerun()

            edited_settings = st.data_editor(st.session_state.settings_df, hide_index=True, width='stretch', height=200)

            if st.button("この条件でシフトを作成する", type="primary"):
                min_l = edited_settings["最小人数"].fillna(0).astype(int).tolist()
                max_l = edited_settings["最大人数"].fillna(1).astype(int).tolist()
                if sum(min_l) > num_attendees: st.warning("※ 設定された最小人数の合計が、出席可能者数を超えています。")
                with st.spinner('計算中...'):
                    res, success = solve_shift_schedule(clean_df, min_l, max_l)
                if success:
                    st.session_state.shift_result = res
                    st.session_state.editing_member = None
                    st.session_state.editing_date = None
                    st.rerun()
                else: st.error("シフトを作成できませんでした。条件を見直してください。")

            # --- ボードUI ---
            if st.session_state.shift_result is not None:
                st.write("")
                c_head, c_status = st.columns([1, 2])
                with c_head: st.subheader("シフト調整結果")
                with c_status:
                    if st.session_state.editing_member:
                        target = st.session_state.editing_member
                        alert_cols = st.columns([4, 1])
                        alert_cols[0].error(f"編集中: **{target['name']}**")
                        if alert_cols[1].button("解除"):
                            st.session_state.editing_member = None
                            st.rerun()
                    elif st.session_state.editing_date:
                        target_date = st.session_state.editing_date
                        alert_cols = st.columns([4, 1])
                        alert_cols[0].error(f"日程選択中: **{target_date}**")
                        if alert_cols[1].button("解除"):
                            st.session_state.editing_date = None
                            st.rerun()
                    else:
                        st.info("部員または日程をクリックして調整できます")
                st.write("")

                current_df = st.session_state.shift_result
                date_to_row = {row['日程']: idx for idx, row in current_df.iterrows()}
                
                max_people_in_day = 0
                for _, row in current_df.iterrows():
                    val = row["担当者"]
                    if pd.notna(val) and str(val) != "":
                        count = len(str(val).split(", "))
                        if count > max_people_in_day: max_people_in_day = count
                col_ratios = [3] * max_people_in_day + [1] 

                for date_idx, date_val in enumerate(dates_list):
                    c_date, c_members = st.columns([1.2, 8], gap="small")
                    
                    # --- 日程ボタン (左端) ---
                    with c_date:
                        date_btn_label = date_val
                        date_btn_type = "secondary"
                        show_as_label = False 
                        on_date_click = "select_date"

                        # A. 部員編集中 (移動先判定)
                        if st.session_state.editing_member:
                            member_a = st.session_state.editing_member['name']
                            date_a = st.session_state.editing_member['source_date']
                            if date_val != date_a:
                                status = get_status(clean_df, date_val, member_a)
                                if status in ["○", "△"]:
                                    date_btn_type = "primary" # 緑 (移動可能)
                                    if status == "△": date_btn_label += "(△)"
                                    on_date_click = "move_member_here"
                                else:
                                    show_as_label = True # 移動不可 -> 紺色ラベル
                            else:
                                show_as_label = True # 元の日程

                        # B. 日程編集中 (自分)
                        elif st.session_state.editing_date == date_val:
                            # 選択解除のためにクリック可能にするが、赤く表示したい
                            # 標準機能では赤くできないため、トグル用ボタンとして表示しつつ
                            # ステータスバーで赤く表示することで代用する仕様に戻します
                            on_date_click = "cancel_date"
                            # 選択中の日程を目立たせたいが、標準ボタンだとSecondaryのまま。
                            # ここは「選択中」と文字を入れてユーザーに伝える
                            date_btn_label = f"{date_val} (選択中)"

                        # 描画
                        if show_as_label:
                             st.markdown(f"<div class='date-label'>{date_val}</div>", unsafe_allow_html=True)
                        else:
                            if st.button(date_btn_label, key=f"d_{date_val}", type=date_btn_type, use_container_width=True):
                                if on_date_click == "select_date":
                                    st.session_state.editing_date = date_val
                                    st.session_state.editing_member = None
                                    st.rerun()
                                elif on_date_click == "cancel_date":
                                    st.session_state.editing_date = None
                                    st.rerun()
                                elif on_date_click == "move_member_here":
                                    # 移動実行
                                    member_a = st.session_state.editing_member['name']
                                    date_a = st.session_state.editing_member['source_date']
                                    row_idx_a = date_to_row[date_a]
                                    row_idx_curr = date_to_row[date_val]
                                    
                                    list_a = current_df.at[row_idx_a, "担当者"].split(", ")
                                    if member_a in list_a: list_a.remove(member_a)
                                    current_df.at[row_idx_a, "担当者"] = ", ".join(list_a)
                                    current_df.at[row_idx_a, "人数"] = len(list_a)
                                    
                                    val_curr = current_df.at[row_idx_curr, "担当者"]
                                    list_curr = val_curr.split(", ") if pd.notna(val_curr) and val_curr != "" else []
                                    list_curr.append(member_a)
                                    list_curr.sort()
                                    current_df.at[row_idx_curr, "担当者"] = ", ".join(list_curr)
                                    current_df.at[row_idx_curr, "人数"] = len(list_curr)
                                    
                                    st.session_state.shift_result = current_df
                                    st.session_state.editing_member = None
                                    st.rerun()

                    # --- 部員ボタン (右側) ---
                    with c_members:
                        row_idx = date_to_row.get(date_val)
                        if row_idx is not None:
                            assigned_val = current_df.at[row_idx, "担当者"]
                            assigned_list = str(assigned_val).split(", ") if pd.notna(assigned_val) and str(assigned_val) != "" else []
                            
                            cols = st.columns(col_ratios, gap="small")
                            
                            for i, member_b in enumerate(assigned_list):
                                is_mem_edit = st.session_state.editing_member is not None
                                is_date_edit = st.session_state.editing_date is not None
                                
                                is_self_mem = (is_mem_edit and 
                                               st.session_state.editing_member['name'] == member_b and 
                                               st.session_state.editing_member['source_date'] == date_val)
                                
                                is_locked = not can_member_move(clean_df, date_val, member_b)
                                
                                # ロック表示 (通常時)
                                if not is_mem_edit and not is_date_edit and is_locked:
                                    cols[i].markdown(f"<div class='locked-member'>🔒{member_b}</div>", unsafe_allow_html=True)
                                    continue 
                                
                                label = f"{member_b}"
                                btn_key = f"b_{date_val}_{member_b}"
                                on_click = "select_member"
                                disabled_state = False
                                btn_type = "secondary"

                                # --- パターンA: 部員編集モード ---
                                if is_mem_edit:
                                    if is_self_mem:
                                        # 自分自身 (赤) -> disabled=True
                                        disabled_state = True 
                                    else:
                                        # 他人
                                        if is_locked:
                                            cols[i].markdown(f"<div class='locked-member'>🔒{member_b}</div>", unsafe_allow_html=True)
                                            continue
                                        
                                        # 交換チェック
                                        mem_a = st.session_state.editing_member['name']
                                        date_a = st.session_state.editing_member['source_date']
                                        if mem_a != member_b and date_val != date_a:
                                            stat_a = get_status(clean_df, date_val, mem_a)
                                            stat_b = get_status(clean_df, date_a, member_b)
                                            if stat_a in ["○", "△"] and stat_b in ["○", "△"]:
                                                btn_type = "primary" # 緑
                                                if stat_b == "△": label += "(△)"
                                                on_click = "swap"

                                # --- パターンB: 日程編集モード ---
                                elif is_date_edit:
                                    tgt_date = st.session_state.editing_date
                                    
                                    if is_locked:
                                        cols[i].markdown(f"<div class='locked-member'>🔒{member_b}</div>", unsafe_allow_html=True)
                                        continue
                                    
                                    if date_val != tgt_date:
                                        stat = get_status(clean_df, tgt_date, member_b)
                                        if stat in ["○", "△"]:
                                            btn_type = "primary" # 緑
                                            if stat == "△": label += "(△)"
                                            on_click = "move_to_date"

                                # 描画
                                if cols[i].button(label, key=btn_key, type=btn_type, disabled=disabled_state, use_container_width=True):
                                    if on_click == "select_member":
                                        st.session_state.editing_member = {'name': member_b, 'source_date': date_val}
                                        st.session_state.editing_date = None
                                        st.rerun()
                                    elif on_click == "swap":
                                        # 交換
                                        mem_a = st.session_state.editing_member['name']
                                        date_a = st.session_state.editing_member['source_date']
                                        idx_a = date_to_row[date_a]
                                        idx_b = row_idx
                                        
                                        l_a = current_df.at[idx_a, "担当者"].split(", ")
                                        if mem_a in l_a: l_a.remove(mem_a)
                                        l_a.append(member_b)
                                        l_a.sort()
                                        current_df.at[idx_a, "担当者"] = ", ".join(l_a)
                                        
                                        l_b = assigned_list[:]
                                        if member_b in l_b: l_b.remove(member_b)
                                        l_b.append(mem_a)
                                        l_b.sort()
                                        current_df.at[idx_b, "担当者"] = ", ".join(l_b)
                                        
                                        st.session_state.shift_result = current_df
                                        st.session_state.editing_member = None
                                        st.rerun()
                                        
                                    elif on_click == "move_to_date":
                                        # 日程へ移動
                                        tgt_date = st.session_state.editing_date
                                        idx_tgt = date_to_row[tgt_date]
                                        
                                        l_src = assigned_list[:]
                                        if member_b in l_src: l_src.remove(member_b)
                                        current_df.at[row_idx, "担当者"] = ", ".join(l_src)
                                        current_df.at[row_idx, "人数"] = len(l_src)
                                        
                                        val_tgt = current_df.at[idx_tgt, "担当者"]
                                        l_tgt = val_tgt.split(", ") if pd.notna(val_tgt) and val_tgt != "" else []
                                        l_tgt.append(member_b)
                                        l_tgt.sort()
                                        current_df.at[idx_tgt, "担当者"] = ", ".join(l_tgt)
                                        current_df.at[idx_tgt, "人数"] = len(l_tgt)
                                        
                                        st.session_state.shift_result = current_df
                                        st.session_state.editing_date = None
                                        st.toast(f"{member_b}さんを{tgt_date}へ移動しました", icon="✅")
                                        st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")