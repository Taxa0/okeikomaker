import streamlit as st
import pandas as pd
import pulp
import streamlit.components.v1 as components
import html as html_lib
import pickle
import io
from datetime import datetime

# ==========================================
# ページ設定 (アイコンはここで変更できます)
# ==========================================
st.set_page_config(
    page_title="お稽古メーカー", 
    page_icon="🍵", 
    layout="wide"
)

# ==========================================
# CSS設定
# ==========================================
st.markdown("""
<style>
    /* 全体の余白 */
    .block-container { padding-top: 3rem; padding-bottom: 2rem; }
    div[data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    div[data-testid="column"] { padding: 0px !important; }
    
    /* --- ボタン共通スタイル (通常ボタン) --- */
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
    
    /* --- 生成ボタン (Primary) --- */
    div.stButton > button[kind="primary"] {
        background-color: #8e44ad !important; /* アメジスト */
        border-color: #8e44ad !important;
        color: white !important;
        height: 50px !important;
        font-size: 18px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #732d91 !important;
        border-color: #732d91 !important;
    }

    /* --- ダウンロードボタン (Save) --- */
    /* 保存ボタンらしい青色にし、目立たせる */
    div[data-testid="stDownloadButton"] > button {
        background-color: #2980b9 !important; /* Save Blue */
        border-color: #2980b9 !important;
        color: white !important;
        font-weight: bold !important;
        height: 45px !important; /* 少し高さを出す */
        font-size: 16px !important;
        border-radius: 5px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #1f618d !important; /* Darker Blue */
        border-color: #1f618d !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.25);
    }
    div[data-testid="stDownloadButton"] > button:active {
        transform: translateY(1px);
        box-shadow: 0 1px 2px rgba(0,0,0,0.2);
    }

    /* --- マーカー判定ルール --- */
    button[aria-label*="\u200b\u200b"][aria-label*="(△)"] {
        background-color: #ffc107 !important; border-color: #ffc107 !important; color: black !important;
    }
    button[aria-label*="\u200b\u200b"][aria-label*="(△)"]:hover { background-color: #e0a800 !important; }

    button[aria-label*="\u200b\u200b"]:not([aria-label*="(△)"]) {
        background-color: #28a745 !important; border-color: #28a745 !important; color: white !important;
    }
    button[aria-label*="\u200b\u200b"]:not([aria-label*="(△)"]):hover { background-color: #218838 !important; }

    button[aria-label*="\u200b"]:not([aria-label*="\u200b\u200b"]) {
        background-color: #ff4b4b !important; border-color: #ff4b4b !important; color: white !important; opacity: 1.0 !important;
    }
    button[aria-label*="\u200b"]:not([aria-label*="\u200b\u200b"]):hover { background-color: #ff3333 !important; }
    button[aria-label*="\u200b"]:disabled { color: white !important; }

    div[data-testid="column"]:nth-of-type(1) div.stButton button:not([aria-label*="\u200b"]) {
        background-color: #2c3e50 !important; border-color: #2c3e50 !important; color: white !important;
    }
    div[data-testid="column"]:nth-of-type(1) div.stButton button:not([aria-label*="\u200b"]):hover { background-color: #1a252f !important; }
    div[data-testid="column"]:nth-of-type(1) div.stButton button:disabled {
        background-color: #2c3e50 !important; border-color: #2c3e50 !important; color: rgba(255, 255, 255, 0.5) !important; opacity: 1.0 !important;
    }

    .locked-member {
        display: flex; align-items: center; justify-content: center;
        width: 100%; height: 34px; background-color: #e9ecef; color: #adb5bd;
        border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 4px;
        font-size: 13px; font-weight: bold; margin-bottom: 2px;
        white-space: nowrap; overflow: hidden; box-sizing: border-box; cursor: not-allowed;
    }
    
    .comment-container {
        border: 1px solid rgba(49, 51, 63, 0.2);
        border-radius: 0.25rem;
        padding: 10px;
        background-color: transparent;
        font-size: 14px;
        line-height: 1.5;
    }
    
    /* 警告エリアのスタイル */
    .stAlert {
        padding: 0.5rem 1rem !important;
    }
    
    /* ツールチップボタンの調整 */
    div[data-testid="stPopover"] > button {
        border: none !important;
        background: transparent !important;
        color: #8e44ad !important;
        font-size: 1.2rem !important;
        padding: 0px !important;
        min-height: 0px !important;
        height: auto !important;
    }
    div[data-testid="stPopover"] > button:hover {
        color: #732d91 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 関数定義 ---

def clean_data(raw_df):
    if len(raw_df) > 0:
        first_col = raw_df.iloc[:, 0].astype(str).fillna("")
        comments_data = {}
        has_comment_row = False
        comment_rows = raw_df[first_col.str.contains('コメント', na=False)]
        
        if not comment_rows.empty:
            has_comment_row = True
            c_row_idx = comment_rows.index[-1] 
            for col in raw_df.columns[1:]:
                val = raw_df.at[c_row_idx, col]
                if pd.notna(val) and str(val).strip() != "":
                    comments_data[col] = str(val).strip()
        
        ignore_keywords = ['最終更新日時', 'コメント']
        mask = ~first_col.apply(lambda x: any(x.startswith(k) for k in ignore_keywords))
        clean_df = raw_df[mask].reset_index(drop=True)
    else:
        clean_df = raw_df
        comments_data = {}
        has_comment_row = False
        
    if len(clean_df.columns) > 0 and "Unnamed" in str(clean_df.columns[0]):
        clean_df.rename(columns={clean_df.columns[0]: '日程'}, inplace=True)
        
    return clean_df, comments_data, has_comment_row

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

def format_comment_text(text):
    if not text: return ""
    safe_text = html_lib.escape(text)
    style_late = "background-color: rgba(255, 75, 75, 0.15); color: #ff4b4b; font-weight: bold; padding: 2px 4px; border-radius: 4px; border: 1px solid rgba(255, 75, 75, 0.5);"
    style_early = "background-color: rgba(33, 150, 243, 0.15); color: #2196f3; font-weight: bold; padding: 2px 4px; border-radius: 4px; border: 1px solid rgba(33, 150, 243, 0.5);"
    safe_text = safe_text.replace("遅れ", f"<span style='{style_late}'>遅れ</span>")
    safe_text = safe_text.replace("遅刻", f"<span style='{style_late}'>遅刻</span>")
    safe_text = safe_text.replace("早退", f"<span style='{style_early}'>早退</span>")
    return safe_text

def solve_shift_schedule(df, min_list, max_list, roster_df=None):
    dates = df.iloc[:, 0].fillna("").astype(str).str.strip().tolist()
    members = df.columns[1:].tolist()
    if len(dates) != len(min_list) or len(dates) != len(max_list): return None, False
    
    prob = pulp.LpProblem("Shift_Scheduler", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("assign", ((d, m) for d in range(len(dates)) for m in range(len(members))), cat='Binary')
    
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
            else: prob += x[d_idx, m_idx] == 0
            preference_scores[(d_idx, m_idx)] = score
            
    penalty_term = 0
    if roster_df is not None and '学年' in roster_df.columns:
        member_grade_map = {str(row['氏名']).strip(): str(row['学年']).strip() for _, row in roster_df.iterrows()}
        unique_grades = {g for g in set(member_grade_map.values()) if g and g.lower() != 'nan'}
        
        excess = pulp.LpVariable.dicts("excess", ((d, g) for d in range(len(dates)) for g in unique_grades), lowBound=0, cat='Integer')
        for d in range(len(dates)):
            for g in unique_grades:
                grade_member_indices = [i for i, m in enumerate(members) if member_grade_map.get(m) == g]
                if grade_member_indices:
                    prob += pulp.lpSum([x[d, i] for i in grade_member_indices]) <= 1 + excess[d, g]
        penalty_term = pulp.lpSum([excess[d, g] for d in range(len(dates)) for g in unique_grades]) * 10

    base_score = pulp.lpSum([x[d, m] * preference_scores[(d, m)] for d in range(len(dates)) for m in range(len(members))])
    prob += base_score - penalty_term
    
    for m_idx in range(len(members)):
        if m_idx in active_members_indices:
            prob += pulp.lpSum([x[d, m_idx] for d in range(len(dates))]) == 1
        else:
            prob += pulp.lpSum([x[d, m_idx] for d in range(len(dates))]) == 0
    
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
if 'comments_data' not in st.session_state: st.session_state.comments_data = {}
if 'has_comment_row' not in st.session_state: st.session_state.has_comment_row = False
if 'clean_df' not in st.session_state: st.session_state.clean_df = None
if 'loaded_resume_name' not in st.session_state: st.session_state.loaded_resume_name = None
if 'confirm_overwrite' not in st.session_state: st.session_state.confirm_overwrite = False
if 'confirm_reset' not in st.session_state: st.session_state.confirm_reset = False

# --- 手順1 (読み込み) ---
st.markdown("### 1. ファイルアップロード")

help_text_densuke = """
伝助のCSVファイルのダウンロード方法:
1. 伝助のページの下の方にある「CSV形式でデータを出力する」をクリックする
2. コメントの「出力する」にチェックを入れ、「CSV形式で登録データを出力する」をクリックする
3. 「CSVデータを取得する」をクリックするとダウンロードができる
"""
uploaded_file = st.file_uploader("**伝助のCSVファイルをアップロード**", type=['csv'], help=help_text_densuke)

help_text_roster = "一行目: 氏名,学年 | 二行目以降: 名前,1 の形式"
uploaded_roster = st.file_uploader("**(任意) 部員名簿CSVファイルをアップロード**", type=['csv'], key="roster", help=help_text_roster)

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

if uploaded_file is not None:
    try:
        try: raw_df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            raw_df = pd.read_csv(uploaded_file, encoding='cp932')
        clean_df, comments_data, has_comment_row = clean_data(raw_df)
        st.session_state.clean_df = clean_df
        st.session_state.comments_data = comments_data
        st.session_state.has_comment_row = has_comment_row
        
        if 'last_filename' not in st.session_state or st.session_state.last_filename != uploaded_file.name:
             st.session_state.last_filename = uploaded_file.name
             st.session_state.shift_result = None
             st.rerun()
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {e}")

st.write("")
with st.expander("📂 保存したファイルから作業を再開"):
    uploaded_resume = st.file_uploader("**バックアップファイル (.okeiko)をアップロード**", type=['okeiko'], key="resume_uploader")
    if uploaded_resume is not None:
        if st.session_state.loaded_resume_name != uploaded_resume.name:
            try:
                uploaded_resume.seek(0)
                resume_data = pickle.load(uploaded_resume)
                st.session_state.clean_df = resume_data.get('clean_df')
                st.session_state.roster_df = resume_data.get('roster_df')
                st.session_state.shift_result = resume_data.get('shift_result')
                st.session_state.settings_df = resume_data.get('settings_df')
                st.session_state.comments_data = resume_data.get('comments_data', {})
                st.session_state.has_comment_row = resume_data.get('has_comment_row', False)
                st.session_state.loaded_resume_name = uploaded_resume.name
                st.session_state.confirm_overwrite = False
                st.session_state.confirm_reset = False
                st.success("作業データを復元しました。下へスクロールして編集を続けてください。")
                st.rerun()
            except Exception as e:
                st.error(f"ファイル読み込みエラー: {e}")
    else:
        st.session_state.loaded_resume_name = None

clean_df = st.session_state.clean_df

# ==========================================
# メイン処理
# ==========================================
if clean_df is not None:
    if len(clean_df.columns) < 2:
        st.error("データ形式エラー: 列数が不足しています")
    else:
        # 変数定義
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

        st.write(""); st.write("---")
        st.markdown("### 2. お稽古の人数を設定")
        
        st.info(f"参加者: **{num_attendees} / {total_members} 名** (全{total_days}日程)")
        
        if st.session_state.roster_df is not None:
            r_df = st.session_state.roster_df
            with st.expander("部員の回答状況を確認する", expanded=True):
                densuke_members = clean_df.columns[1:].tolist()
                roster_members_list = [str(n).strip() for n in r_df['氏名'].tolist()]
                unknown_in_densuke = [m for m in densuke_members if m not in roster_members_list]
                if unknown_in_densuke:
                    st.warning(f"⚠️ 【{len(unknown_in_densuke)}名】 **名簿に登録されていない名前が伝助に見つかりました (表記ゆれの可能性があります):**\n\n{', '.join(unknown_in_densuke)}")
                unanswered_members = [m for m in roster_members_list if m not in densuke_members]
                if unanswered_members:
                    st.error(f"🚨 【{len(unanswered_members)}名】 **未回答者:**\n\n{', '.join(unanswered_members)}")
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

        if st.session_state.get('settings_df') is None or len(st.session_state.settings_df) != total_days:
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

        generate_clicked = st.button("🔮 お稽古生成 🔮", type="primary", use_container_width=True)
        
        if generate_clicked:
            if st.session_state.shift_result is not None:
                st.session_state.confirm_overwrite = True
            else:
                st.session_state.confirm_overwrite = False
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
                else: st.error("お稽古を作成できませんでした。条件を見直してください。")

        if st.session_state.confirm_overwrite:
            st.warning("⚠️ **すでにお稽古が生成されています。**\n\n新しく生成すると、現在の編集内容はすべて失われます。よろしいですか？")
            col_ov_y, col_ov_n = st.columns([1, 1])
            if col_ov_y.button("はい、上書き生成します", use_container_width=True):
                st.session_state.confirm_overwrite = False
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
                else: st.error("お稽古を作成できませんでした。条件を見直してください。")
            
            if col_ov_n.button("いいえ", use_container_width=True):
                st.session_state.confirm_overwrite = False
                st.rerun()

        # ------------------------------------------------
        # 3. 生成結果・編集
        # ------------------------------------------------
        if st.session_state.shift_result is not None:
            js_code = """
            <script>
                function applyColors() {
                    const buttons = window.parent.document.querySelectorAll('button');
                    buttons.forEach(btn => {
                        const text = btn.innerText;
                        if (text.includes('\u200b\u200b')) {
                            if (text.includes('(△)')) {
                                btn.style.backgroundColor = '#ffc107'; btn.style.color = 'black'; btn.style.borderColor = '#ffc107';
                            } else {
                                btn.style.backgroundColor = '#28a745'; btn.style.color = 'white'; btn.style.borderColor = '#28a745';
                            }
                            return;
                        } 
                        if (text.includes('\u200b')) {
                            btn.style.backgroundColor = '#ff4b4b'; btn.style.color = 'white'; btn.style.borderColor = '#ff4b4b'; btn.style.opacity = '1.0';
                            return;
                        } 
                        if (!text.includes('生成') && !text.includes('解除') && !text.includes('保存') && !text.includes('リセット') && !text.includes('はい') && !text.includes('いいえ') && !text.includes('キャンセル')) {
                             btn.style.backgroundColor = ''; btn.style.color = ''; btn.style.borderColor = '';
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
            
            st.caption("PCもしくはiPadでの編集をお勧めします。スマートフォンの場合は画面を横向きにしてください。")
            st.write("")

            current_df = st.session_state.shift_result.copy()
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
                            if member_b in grade_map: display_name = f"{grade_map[member_b]}.{member_b}"
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
                                    mem_a = st.session_state.editing_member['name']
                                    date_a = st.session_state.editing_member['source_date']
                                    if mem_a != member_b and date_val != date_a:
                                        stat_a = get_status(clean_df, date_val, mem_a)
                                        stat_b = get_status(clean_df, date_a, member_b)
                                        if stat_a in ["○", "△"] and stat_b in ["○", "△"]:
                                            label += "\u200b\u200b"
                                            on_click = "swap"
                                        elif is_locked:
                                            lock_label = member_b
                                            if member_b in grade_map: lock_label = f"{grade_map[member_b]}.{member_b}"
                                            cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                            continue
                                    elif is_locked:
                                        cols[i].markdown(f"<div class='locked-member'>🔒{member_b}</div>", unsafe_allow_html=True)
                                        continue
                            elif is_date_edit:
                                tgt_date = st.session_state.editing_date
                                if date_val != tgt_date:
                                    stat = get_status(clean_df, tgt_date, member_b)
                                    if stat in ["○", "△"]:
                                        label += "\u200b\u200b"
                                        on_click = "move_to_date"
                                    elif is_locked:
                                        lock_label = member_b
                                        if member_b in grade_map: lock_label = f"{grade_map[member_b]}.{member_b}"
                                        cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                        continue
                                elif is_locked:
                                    cols[i].markdown(f"<div class='locked-member'>🔒{member_b}</div>", unsafe_allow_html=True)
                                    continue
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
            
            st.write("---")
            st.subheader("テキストプレビュー")
            st.caption("※(△)について、伝助のコメントを確認し、「遅れ」もしくは「早退」に書き換えた上でご利用ください。")
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
            
            st.code(text_output, language='text')

            st.write("---")
            st.subheader("伝助コメント欄")
            
            if not st.session_state.has_comment_row:
                st.warning("※ 伝助のCSVファイルにコメントの行が存在しませんでした")
            else:
                comments_html_lines = []
                cm_data = st.session_state.comments_data
                assigned_members_set = set()
                
                for _, row in current_df.iterrows():
                    date_str = row['日程']
                    raw_members = row['担当者']
                    if raw_members:
                        member_list = raw_members.split(", ")
                        for m in member_list:
                            assigned_members_set.add(m)
                            if m in cm_data:
                                fmt_comment = format_comment_text(cm_data[m])
                                comments_html_lines.append(f"<div>{date_str} {m}：{fmt_comment}</div>")
                
                densuke_members = clean_df.columns[1:].tolist()
                for m in densuke_members:
                    if m not in assigned_members_set:
                        if m in cm_data:
                            fmt_comment = format_comment_text(cm_data[m])
                            comments_html_lines.append(f"<div style='color: #808080;'>(お休み) {m}：{fmt_comment}</div>")
                
                if comments_html_lines:
                    full_html = "".join(comments_html_lines)
                    st.markdown(f'<div class="comment-container">{full_html}</div>', unsafe_allow_html=True)
                else:
                    st.info("表示すべきコメントはありません")
            
            st.write("")
            st.write("")
            save_data = {
                'clean_df': st.session_state.clean_df,
                'roster_df': st.session_state.roster_df,
                'shift_result': st.session_state.shift_result,
                'settings_df': st.session_state.settings_df,
                'comments_data': st.session_state.comments_data,
                'has_comment_row': st.session_state.has_comment_row
            }
            buffer = io.BytesIO()
            pickle.dump(save_data, buffer)
            
            today_str = datetime.now().strftime('%Y%m%d')
            file_name = f"{today_str}_backup.okeiko"
            
            col_dl_L, col_dl_R = st.columns([3, 1])
            with col_dl_R:
                st.download_button("💾 作業を保存", data=buffer, file_name=file_name, mime="application/octet-stream", use_container_width=True)
