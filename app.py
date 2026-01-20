import streamlit as st
import pandas as pd
import pulp
import streamlit.components.v1 as components

# ページ設定
st.set_page_config(page_title="🍵 お稽古メーカー", layout="wide")

# ==========================================
# CSS設定 (ボタンデザイン・色制御)
# ==========================================
st.markdown("""
<style>
    /* 全体の余白 */
    .block-container { padding-top: 3rem; padding-bottom: 2rem; }
    div[data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    div[data-testid="column"] { padding: 0px !important; }
    
    /* ボタン共通スタイル */
    .stButton { margin: 0px !important; padding: 0px !important; }
    .stButton button {
        height: 34px !important; min-height: 34px !important;
        padding: 0px 4px !important; font-weight: bold !important;
        font-size: 13px !important; border-radius: 4px !important;
        line-height: 1 !important;
        border: 1px solid rgba(49, 51, 63, 0.2);
    }
    .stButton button div[data-testid="stMarkdownContainer"] p {
        width: 100%; text-align: center; margin: 0px;
    }
    
    /* ---------------------------------------------------
       特別なボタンの色設定
       --------------------------------------------------- */
    
    /* 生成ボタン (Primary) */
    div.stButton > button[kind="primary"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
        color: white !important;
        height: 50px !important;
        font-size: 18px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #0056b3 !important;
        border-color: #0056b3 !important;
    }

    /* ---------------------------------------------------
       カラーリングルール (マーカー判定)
       --------------------------------------------------- */

    /* 1. 移動可能 (緑/黄) */
    button[aria-label*="\u200b\u200b"][aria-label*="(△)"] {
        background-color: #ffc107 !important;
        border-color: #ffc107 !important;
        color: black !important;
    }
    button[aria-label*="\u200b\u200b"][aria-label*="(△)"]:hover {
        background-color: #e0a800 !important;
    }
    button[aria-label*="\u200b\u200b"]:not([aria-label*="(△)"]) {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
        color: white !important;
    }
    button[aria-label*="\u200b\u200b"]:not([aria-label*="(△)"]):hover {
        background-color: #218838 !important;
    }

    /* 2. 選択中 (赤) */
    button[aria-label*="\u200b"]:not([aria-label*="\u200b\u200b"]) {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: white !important;
        opacity: 1.0 !important;
    }
    button[aria-label*="\u200b"]:not([aria-label*="\u200b\u200b"]):hover {
        background-color: #ff3333 !important;
    }
    button[aria-label*="\u200b"]:disabled {
        color: white !important;
    }

    /* 3. 日程ボタン (紺) */
    div[data-testid="column"]:nth-of-type(1) div.stButton button:not([aria-label*="\u200b"]) {
        background-color: #2c3e50 !important;
        border-color: #2c3e50 !important;
        color: white !important;
    }
    div[data-testid="column"]:nth-of-type(1) div.stButton button:not([aria-label*="\u200b"]):hover {
        background-color: #1a252f !important;
    }
    div[data-testid="column"]:nth-of-type(1) div.stButton button:disabled {
        background-color: #2c3e50 !important;
        border-color: #2c3e50 !important;
        color: rgba(255, 255, 255, 0.5) !important;
        opacity: 1.0 !important;
    }

    /* ロックされた部員 (グレー) */
    .locked-member {
        display: flex; align-items: center; justify-content: center;
        width: 100%; height: 34px; background-color: #e9ecef; color: #adb5bd;
        border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 4px;
        font-size: 13px; font-weight: bold; margin-bottom: 2px;
        white-space: nowrap; overflow: hidden; box-sizing: border-box; cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)

# --- 関数定義 ---

def clean_data(raw_df):
    if len(raw_df) > 0:
        first_col = raw_df.iloc[:, 0].astype(str).fillna("")
        ignore_keywords = ['最終更新日時', 'コメント']
        mask = ~first_col.apply(lambda x: any(x.startswith(k) for k in ignore_keywords))
        clean_df = raw_df[mask].reset_index(drop=True)
    else:
        clean_df = raw_df
    if len(clean_df.columns) > 0 and "Unnamed" in str(clean_df.columns[0]):
        clean_df.rename(columns={clean_df.columns[0]: '日程'}, inplace=True)
    return clean_df

def sort_members_by_roster(member_list, roster_df):
    if not member_list: return []
    if roster_df is None:
        member_list.sort()
        return member_list
    roster_names = [str(n).strip() for n in roster_df['氏名'].tolist()]
    rank_map = {name: i for i, name in enumerate(roster_names)}
    def get_rank(name): return rank_map.get(name, 999999)
    member_list.sort(key=get_rank)
    return member_list

def solve_shift_schedule(df, min_list, max_list, roster_df=None):
    dates = df.iloc[:, 0].fillna("").astype(str).str.strip().tolist()
    members = df.columns[1:].tolist()
    if len(dates) != len(min_list) or len(dates) != len(max_list): return None, False
    
    prob = pulp.LpProblem("Shift_Scheduler", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("assign", ((d, m) for d in range(len(dates)) for m in range(len(members))), cat='Binary')
    
    # ★追加: 参加意思のある部員(○か△が少なくとも1つある)を特定
    active_members_indices = []
    for m_idx, member in enumerate(members):
        s_series = df[member].astype(str).str.strip()
        if any(s in ['○', '△'] for s in s_series):
            active_members_indices.append(m_idx)

    preference_scores = {}
    for d_idx, date in enumerate(dates):
        for m_idx, member in enumerate(members):
            val = df.iloc[d_idx, m_idx + 1]
            status = str(val).strip() if pd.notna(val) else "-"
            
            score = 0
            if status == "○": score = 2
            elif status == "△": score = 1
            else: 
                # 参加不可の日は割り当てない
                prob += x[d_idx, m_idx] == 0
            preference_scores[(d_idx, m_idx)] = score
            
    # 目的関数
    prob += pulp.lpSum([x[d, m] * preference_scores[(d, m)] for d in range(len(dates)) for m in range(len(members))])
    
    # ★修正: 参加意思のある部員は【必ず1回】、それ以外は0回
    for m_idx in range(len(members)):
        if m_idx in active_members_indices:
            prob += pulp.lpSum([x[d, m_idx] for d in range(len(dates))]) == 1
        else:
            prob += pulp.lpSum([x[d, m_idx] for d in range(len(dates))]) == 0
    
    # 人数制約
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
            assigned = sort_members_by_roster(assigned, roster_df)
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
st.title("🍵 お稽古メーカー")

if 'shift_result' not in st.session_state: st.session_state.shift_result = None
if 'editing_member' not in st.session_state: st.session_state.editing_member = None 
if 'editing_date' not in st.session_state: st.session_state.editing_date = None
if 'roster_df' not in st.session_state: st.session_state.roster_df = None

# --- 手順1 ---
st.markdown("### 1. 伝助からCSVファイルをダウンロードし、以下にアップロードする")
uploaded_file = st.file_uploader("CSVファイル", type=['csv'], label_visibility="collapsed")

st.markdown("**(任意) 部員名簿CSVをアップロード**")
st.caption("一行目: `氏名,学年` | 二行目以降: `名前,1` の形式")
uploaded_roster = st.file_uploader("部員名簿", type=['csv'], label_visibility="collapsed", key="roster")

clean_df = None

# 名簿読み込み
if uploaded_roster is not None:
    try:
        try: roster_df = pd.read_csv(uploaded_roster)
        except UnicodeDecodeError:
            uploaded_roster.seek(0)
            roster_df = pd.read_csv(uploaded_roster, encoding='cp932')
        if '氏名' not in roster_df.columns:
            st.error("名簿CSVに「氏名」という列が見つかりません。")
        else:
            st.session_state.roster_df = roster_df
    except Exception as e:
        st.error(f"名簿読み込みエラー: {e}")

# 伝助読み込み
if uploaded_file is not None:
    try:
        try: raw_df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            raw_df = pd.read_csv(uploaded_file, encoding='cp932')
        clean_df = clean_data(raw_df)
        if 'last_filename' not in st.session_state or st.session_state.last_filename != uploaded_file.name:
             st.session_state.last_filename = uploaded_file.name
             st.session_state.shift_result = None
             st.rerun()
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {e}")

if clean_df is not None:
    if len(clean_df.columns) < 2:
            st.error("データ形式エラー: 列数が不足しています")
    else:
        members_list = clean_df.columns[1:].tolist()
        dates_list = clean_df.iloc[:, 0].fillna("").astype(str).str.strip().tolist()
        total_members = int(len(members_list))
        total_days = int(len(dates_list))
        attendees = []
        for m in members_list:
            s_series = clean_df[m].astype(str).str.strip()
            if any(s in ['○', '△'] for s in s_series): attendees.append(m)
        num_attendees = len(attendees)

        if total_days > 0 and num_attendees > 0:
            default_bulk_max = (num_attendees // total_days) + 1
            default_bulk_min = max(0, default_bulk_max - 2)
        else:
            default_bulk_max = 1; default_bulk_min = 0
        safe_input_max = total_members if total_members > 0 else 1
        default_bulk_max = min(default_bulk_max, safe_input_max)
        default_bulk_min = min(default_bulk_min, safe_input_max)

        # --- 手順2 ---
        st.write(""); st.write("---")
        st.markdown("### 2. お稽古の人数を設定する")
        st.info(f"出席可能者: **{num_attendees} / {total_members} 名** (全{total_days}日程)")
        
        # 名簿チェック
        if st.session_state.roster_df is not None:
            r_df = st.session_state.roster_df
            with st.expander("部員の回答状況を確認する", expanded=True):
                densuke_members = clean_df.columns[1:].tolist()
                
                roster_members_list = [str(n).strip() for n in r_df['氏名'].tolist()]
                
                # 1. 伝助にあるが名簿にない
                unknown_in_densuke = [m for m in densuke_members if m not in roster_members_list]
                if unknown_in_densuke:
                    st.warning(f"⚠️ **名簿に登録されていない名前が伝助に見つかりました ({len(unknown_in_densuke)}名 / 表記ゆれの可能性があります):**\n\n{', '.join(unknown_in_densuke)}")

                # 2. 名簿にあるが伝助にない
                unanswered_members = [m for m in roster_members_list if m not in densuke_members]
                if unanswered_members:
                    st.error(f"🚨 **未回答者 ({len(unanswered_members)}名):**\n\n{', '.join(unanswered_members)}")

                # 3. 回答状況表
                status_data = []
                for _, row in r_df.iterrows():
                    name = str(row.get('氏名', '')).strip()
                    if not name: continue
                    if name not in densuke_members: status = "未回答"
                    else:
                        person_vals = clean_df[name].astype(str).tolist()
                        if any(v.strip() in ['○', '△'] for v in person_vals): status = "〇"
                        else: status = "欠席"
                    status_data.append({"氏名": name, "状況": status})
                
                if status_data:
                    st.dataframe(pd.DataFrame(status_data), hide_index=True, use_container_width=True)

        if 'settings_df' not in st.session_state or len(st.session_state.settings_df) != total_days:
            st.session_state.settings_df = pd.DataFrame({
                "日程": dates_list, 
                "最小人数": [default_bulk_min] * len(dates_list), 
                "最大人数": [default_bulk_max] * len(dates_list)
            })

        col1, col2, col3 = st.columns([1,1,1])
        with col1: b_min = st.number_input("一括最小", 0, safe_input_max, default_bulk_min)
        with col2: b_max = st.number_input("一括最大", 1, safe_input_max, default_bulk_max)
        with col3:
            st.write(""); st.write("")
            if st.button("全日程に適用"):
                st.session_state.settings_df["最小人数"] = b_min
                st.session_state.settings_df["最大人数"] = b_max
                st.rerun()

        edited_settings = st.data_editor(st.session_state.settings_df, hide_index=True, width='stretch', height=200)

        if st.button("お稽古生成", type="primary", use_container_width=True):
            min_l = edited_settings["最小人数"].fillna(0).astype(int).tolist()
            max_l = edited_settings["最大人数"].fillna(1).astype(int).tolist()
            if sum(min_l) > num_attendees: st.warning("※ 設定された最小人数の合計が、出席可能者数を超えています。")
            with st.spinner('計算中...'):
                res, success = solve_shift_schedule(clean_df, min_l, max_l, st.session_state.roster_df)
            if success:
                st.session_state.shift_result = res
                st.session_state.editing_member = None
                st.session_state.editing_date = None
                st.rerun()
            else:
                # ★修正: エラーメッセージ
                st.error("お稽古を作成できませんでした。参加希望者全員を1回ずつ割り当てるための枠が足りないか、日程の都合がつきません。人数の上限を増やすなど条件を見直してください。")

        # --- 手順3 ---
        if st.session_state.shift_result is not None:
            # JS
            js_code = """
            <script>
                function applyColors() {
                    const buttons = window.parent.document.querySelectorAll('button');
                    buttons.forEach(btn => {
                        const text = btn.innerText;
                        if (text.includes('\u200b\u200b')) {
                            if (text.includes('(△)')) {
                                btn.style.backgroundColor = '#ffc107';
                                btn.style.color = 'black';
                                btn.style.borderColor = '#ffc107';
                            } else {
                                btn.style.backgroundColor = '#28a745';
                                btn.style.color = 'white';
                                btn.style.borderColor = '#28a745';
                            }
                            return;
                        } 
                        if (text.includes('\u200b')) {
                            btn.style.backgroundColor = '#ff4b4b';
                            btn.style.color = 'white';
                            btn.style.borderColor = '#ff4b4b';
                            btn.style.opacity = '1.0';
                            return;
                        } 
                        if (!text.includes('生成') && !text.includes('解除')) {
                             btn.style.backgroundColor = '';
                             btn.style.color = '';
                             btn.style.borderColor = '';
                        }
                    });
                }
                const observer = new MutationObserver(() => { applyColors(); });
                observer.observe(window.parent.document.body, { childList: true, subtree: true });
                setInterval(applyColors, 100);
                applyColors();
            </script>
            """
            components.html(js_code, height=0, width=0)
            
            st.write(""); st.write("---")
            c_head, c_status = st.columns([1, 1.5])
            with c_head: st.subheader("3. 生成されたお稽古・編集")
            with c_status:
                if st.session_state.editing_member:
                    target = st.session_state.editing_member
                    alert_cols = st.columns([3, 1], gap="small")
                    with alert_cols[0]: st.error(f"編集中: **{target['name']}**", icon="✏️")
                    with alert_cols[1]:
                        if st.button("解除", key="cancel_btn", use_container_width=True):
                            st.session_state.editing_member = None
                            st.rerun()
                elif st.session_state.editing_date:
                    target_date = st.session_state.editing_date
                    alert_cols = st.columns([3, 1], gap="small")
                    with alert_cols[0]: st.error(f"日程選択中: **{target_date}**", icon="📅")
                    with alert_cols[1]:
                        if st.button("解除", key="cancel_btn", use_container_width=True):
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
            
            grade_map = {}
            if st.session_state.roster_df is not None:
                try:
                    for _, r in st.session_state.roster_df.iterrows():
                        grade_map[str(r['氏名']).strip()] = str(r['学年']).strip()
                except: pass

            for date_idx, date_val in enumerate(dates_list):
                c_date, c_members = st.columns([1.2, 8], gap="small")
                
                with c_date:
                    btn_label = date_val
                    disabled_state = False
                    on_click = "select_date"

                    if st.session_state.editing_member:
                        member_a = st.session_state.editing_member['name']
                        date_a = st.session_state.editing_member['source_date']
                        if date_val != date_a:
                            status = get_status(clean_df, date_val, member_a)
                            if status in ["○", "△"]:
                                btn_label += "\u200b\u200b"
                                if status == "△": btn_label += "(△)"
                                on_click = "move_member_here"
                            else: disabled_state = True
                        else: disabled_state = True
                    elif st.session_state.editing_date == date_val:
                        btn_label += "\u200b"
                        on_click = "cancel_date"

                    if st.button(btn_label, key=f"d_{date_val}", disabled=disabled_state, use_container_width=True):
                        if on_click == "select_date":
                            st.session_state.editing_date = date_val
                            st.session_state.editing_member = None
                            st.rerun()
                        elif on_click == "cancel_date":
                            st.session_state.editing_date = None
                            st.rerun()
                        elif on_click == "move_member_here":
                            member_a = st.session_state.editing_member['name']
                            date_a = st.session_state.editing_member['source_date']
                            row_idx_a = date_to_row[date_a]; row_idx_curr = date_to_row[date_val]
                            list_a = current_df.at[row_idx_a, "担当者"].split(", ")
                            if member_a in list_a: list_a.remove(member_a)
                            current_df.at[row_idx_a, "担当者"] = ", ".join(list_a)
                            current_df.at[row_idx_a, "人数"] = len(list_a)
                            val_curr = current_df.at[row_idx_curr, "担当者"]
                            list_curr = val_curr.split(", ") if pd.notna(val_curr) and val_curr != "" else []
                            list_curr.append(member_a)
                            list_curr = sort_members_by_roster(list_curr, st.session_state.roster_df)
                            current_df.at[row_idx_curr, "担当者"] = ", ".join(list_curr)
                            current_df.at[row_idx_curr, "人数"] = len(list_curr)
                            st.session_state.shift_result = current_df
                            st.session_state.editing_member = None
                            st.rerun()

                with c_members:
                    row_idx = date_to_row.get(date_val)
                    if row_idx is not None:
                        assigned_val = current_df.at[row_idx, "担当者"]
                        assigned_list = str(assigned_val).split(", ") if pd.notna(assigned_val) and str(assigned_val) != "" else []
                        cols = st.columns(col_ratios, gap="small")
                        
                        for i, member_b in enumerate(assigned_list):
                            is_mem_edit = st.session_state.editing_member is not None
                            is_date_edit = st.session_state.editing_date is not None
                            is_self_mem = (is_mem_edit and st.session_state.editing_member['name'] == member_b and st.session_state.editing_member['source_date'] == date_val)
                            is_locked = not can_member_move(clean_df, date_val, member_b)
                            
                            if not is_mem_edit and not is_date_edit and is_locked:
                                lock_label = member_b
                                if member_b in grade_map: lock_label = f"{grade_map[member_b]}.{member_b}"
                                cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                continue 
                            
                            display_name = member_b
                            if member_b in grade_map:
                                display_name = f"{grade_map[member_b]}.{member_b}"
                            
                            status_this_day = get_status(clean_df, date_val, member_b)
                            label = display_name
                            if status_this_day == "△": label += "(△)"

                            btn_key = f"b_{date_val}_{member_b}"
                            on_click = "select_member"
                            disabled_state = False
                            
                            if is_mem_edit:
                                if is_self_mem:
                                    label += "\u200b"
                                    on_click = "cancel_member"
                                else:
                                    if is_locked:
                                        lock_label = member_b
                                        if member_b in grade_map: lock_label = f"{grade_map[member_b]}.{member_b}"
                                        cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                        continue
                                    mem_a = st.session_state.editing_member['name']
                                    date_a = st.session_state.editing_member['source_date']
                                    if mem_a != member_b and date_val != date_a:
                                        stat_a = get_status(clean_df, date_val, mem_a)
                                        stat_b = get_status(clean_df, date_a, member_b)
                                        if stat_a in ["○", "△"] and stat_b in ["○", "△"]:
                                            label += "\u200b\u200b"
                                            on_click = "swap"

                            elif is_date_edit:
                                tgt_date = st.session_state.editing_date
                                if is_locked:
                                    lock_label = member_b
                                    if member_b in grade_map: lock_label = f"{grade_map[member_b]}.{member_b}"
                                    cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                    continue
                                if date_val != tgt_date:
                                    stat = get_status(clean_df, tgt_date, member_b)
                                    if stat in ["○", "△"]:
                                        label += "\u200b\u200b"
                                        on_click = "move_to_date"

                            if cols[i].button(label, key=btn_key, disabled=disabled_state, use_container_width=True):
                                if on_click == "select_member":
                                    st.session_state.editing_member = {'name': member_b, 'source_date': date_val}
                                    st.session_state.editing_date = None
                                    st.rerun()
                                elif on_click == "cancel_member":
                                    st.session_state.editing_member = None
                                    st.rerun()
                                elif on_click == "swap":
                                    mem_a = st.session_state.editing_member['name']
                                    date_a = st.session_state.editing_member['source_date']
                                    idx_a = date_to_row[date_a]; idx_b = row_idx
                                    l_a = current_df.at[idx_a, "担当者"].split(", ")
                                    if mem_a in l_a: l_a.remove(mem_a)
                                    l_a.append(member_b)
                                    l_a = sort_members_by_roster(l_a, st.session_state.roster_df)
                                    current_df.at[idx_a, "担当者"] = ", ".join(l_a)
                                    l_b = assigned_list[:]
                                    if member_b in l_b: l_b.remove(member_b)
                                    l_b.append(mem_a)
                                    l_b = sort_members_by_roster(l_b, st.session_state.roster_df)
                                    current_df.at[idx_b, "担当者"] = ", ".join(l_b)
                                    st.session_state.shift_result = current_df
                                    st.session_state.editing_member = None
                                    st.rerun()
                                elif on_click == "move_to_date":
                                    tgt_date = st.session_state.editing_date
                                    idx_tgt = date_to_row[tgt_date]
                                    l_src = assigned_list[:]
                                    if member_b in l_src: l_src.remove(member_b)
                                    current_df.at[row_idx, "担当者"] = ", ".join(l_src)
                                    current_df.at[row_idx, "人数"] = len(l_src)
                                    val_tgt = current_df.at[idx_tgt, "担当者"]
                                    l_tgt = val_tgt.split(", ") if pd.notna(val_tgt) and val_tgt != "" else []
                                    l_tgt.append(member_b)
                                    l_tgt = sort_members_by_roster(l_tgt, st.session_state.roster_df)
                                    current_df.at[idx_tgt, "担当者"] = ", ".join(l_tgt)
                                    current_df.at[idx_tgt, "人数"] = len(l_tgt)
                                    st.session_state.shift_result = current_df
                                    st.session_state.editing_date = None
                                    st.rerun()
            
            # --- テキストプレビュー ---
            st.write("---")
            st.markdown("#### テキストプレビュー (コピー用)")
            st.caption("※(△)について、伝助のコメントを確認した上で、「遅れ」もしくは「早退」に書き換えてください。")
            text_output = ""
            for _, row in current_df.iterrows():
                date_str = row['日程']
                raw_members = row['担当者']
                if raw_members:
                    member_list = raw_members.split(", ")
                    formatted_members = []
                    for member in member_list:
                        status = get_status(clean_df, date_str, member)
                        if status == "△": formatted_members.append(f"{member}(△)")
                        else: formatted_members.append(member)
                    
                    members_str_jp = "、".join(formatted_members)
                    text_output += f"{date_str}{members_str_jp}\n"
            
            st.text_area("以下のテキストをコピーして使用してください", text_output, height=300, label_visibility="collapsed")
