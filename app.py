import streamlit as st
import pandas as pd
import pulp
import streamlit.components.v1 as components
import html as html_lib
import pickle
import io
from datetime import datetime

# ==========================================
# ページ設定
# ==========================================
st.set_page_config(
    page_title="お稽古メーカー", 
    page_icon="🍵", 
    layout="wide"
)

# ==========================================
# JavaScript設定 (アイコン設定 & 色分けロジック)
# ==========================================
# ボタンの色制御を強化( !important を付与)して、確実に色が反映されるように修正
js_code = """
<script>
    // 1. Apple Touch Iconの設定
    function setAppleTouchIcon(emoji) {
        const canvas = document.createElement('canvas');
        canvas.width = 192;
        canvas.height = 192;
        const ctx = canvas.getContext('2d');
        ctx.font = '160px serif';
        ctx.fillText(emoji, 10, 160);
        const dataUrl = canvas.toDataURL();
        const head = window.parent.document.querySelector('head');
        const existing = head.querySelector('link[rel="apple-touch-icon"]');
        if (existing) { existing.remove(); }
        const link = window.parent.document.createElement('link');
        link.rel = 'apple-touch-icon';
        link.href = dataUrl;
        head.appendChild(link);
    }
    setAppleTouchIcon('🍵');

    // 2. ボタンの色付けロジック (常時監視)
    function applyColors() {
        const buttons = window.parent.document.querySelectorAll('button');
        buttons.forEach(btn => {
            const text = btn.innerText;
            
            // --- 日付ボタン (\\u200E を含む) ---
            if (text.includes('\\u200E')) {
                // ダブルマーカー (\\u200b\\u200b) = 移動候補
                if (text.includes('\\u200b\\u200b')) {
                    if (text.includes('(△)')) {
                        // 黄色 (警告色)
                        btn.style.setProperty('background-color', '#ffc107', 'important');
                        btn.style.setProperty('color', 'black', 'important');
                        btn.style.setProperty('border-color', '#ffc107', 'important');
                    } else {
                        // 緑色 (移動可能)
                        btn.style.setProperty('background-color', '#28a745', 'important');
                        btn.style.setProperty('color', 'white', 'important');
                        btn.style.setProperty('border-color', '#28a745', 'important');
                    }
                } 
                // シングルマーカー (\\u200b) = 選択中
                else if (text.includes('\\u200b')) {
                    // 赤色
                    btn.style.setProperty('background-color', '#ff4b4b', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                    btn.style.setProperty('border-color', '#ff4b4b', 'important');
                } 
                // マーカーなし = 通常 (濃いグレー)
                else {
                    btn.style.setProperty('background-color', '#5D6D7E', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                    btn.style.setProperty('border-color', '#5D6D7E', 'important');
                }
                return;
            }

            // --- メンバーボタン: 選択中 (シングルマーカー \\u200b) ---
            if (text.includes('\\u200b')) {
                if (!text.includes('\\u200b\\u200b')) {
                    btn.style.setProperty('background-color', '#ff4b4b', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                    btn.style.setProperty('border-color', '#ff4b4b', 'important');
                    btn.style.setProperty('opacity', '1.0', 'important');
                    return;
                }
            } 

            // --- メンバーボタン: 交換/移動候補 (ダブルマーカー \\u200b\\u200b) ---
            if (text.includes('\\u200b\\u200b')) {
                if (text.includes('(△)')) {
                    btn.style.setProperty('background-color', '#ffc107', 'important');
                    btn.style.setProperty('color', 'black', 'important');
                    btn.style.setProperty('border-color', '#ffc107', 'important');
                } else {
                    btn.style.setProperty('background-color', '#28a745', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                    btn.style.setProperty('border-color', '#28a745', 'important');
                }
                return;
            } 

            // --- それ以外のボタン (デフォルトに戻す) ---
            // 特定のボタン(機能ボタン)は色を変えないように除外リストで判定
            if (!text.includes('生成') && !text.includes('解除') && !text.includes('保存') && !text.includes('リセット') && !text.includes('はい') && !text.includes('いいえ') && !text.includes('キャンセル') && !text.includes('CSV') && !text.includes('名簿') && !text.includes('バックアップ')) {
                 btn.style.removeProperty('background-color');
                 btn.style.removeProperty('color');
                 btn.style.removeProperty('border-color');
            }
        });
    }
    
    // 監視設定
    const observer = new MutationObserver(() => { applyColors(); });
    observer.observe(window.parent.document.body, { childList: true, subtree: true });
    // 念のため定期実行も入れておく
    setInterval(applyColors, 200);
    applyColors();
</script>
"""
components.html(js_code, height=0, width=0)

st.markdown("""
<style>
    /* 全体の余白 */
    .block-container { padding-top: 3rem; padding-bottom: 2rem; }
    div[data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    div[data-testid="column"] { padding: 0px !important; }
    
    /* --- ボタン共通スタイル --- */
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
        background-color: #8e44ad !important;
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
    [data-testid="stDownloadButton"] button {
        background-color: #8e44ad !important;
        border-color: #8e44ad !important;
        color: white !important;
        font-weight: bold !important;
        height: 45px !important;
        font-size: 16px !important;
        border-radius: 5px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    [data-testid="stDownloadButton"] button:hover {
        background-color: #732d91 !important;
        border-color: #732d91 !important;
    }
    [data-testid="stDownloadButton"] button:active {
        background-color: #732d91 !important;
    }

    /* --- マーカー判定ルール (CSSも念のため残すがJS優先) --- */
    /* JSの !important により基本的にJSが勝つ */

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
    
    .stAlert { padding: 0.5rem 1rem !important; }
    
    div[data-testid="stPopover"] > button {
        border: none !important;
        background: transparent !important;
        color: #8e44ad !important;
        font-size: 1.2rem !important;
        padding: 0px !important;
        min-height: 0px !important;
        height: auto !important;
    }
    div[data-testid="stPopover"] > button:hover { color: #732d91 !important; }
    
    /* アコーディオン内の数値入力のみラベルを非表示 */
    div[data-testid="stExpanderDetails"] div[data-testid="stNumberInput"] label {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# --- 関数定義 ---

# コールバック関数: グローバル設定が変更されたらDataFrameを更新する
def apply_global_settings():
    if 'settings_df' in st.session_state and st.session_state.settings_df is not None:
        val_min = st.session_state.global_min
        val_max = st.session_state.global_max
        
        # DataFrameの更新
        st.session_state.settings_df["最小人数"] = val_min
        st.session_state.settings_df["最大人数"] = val_max
        
        # 個別ウィジェット用セッションステートの更新
        # これをやらないと、テーブル表示の数値入力ボックスに値が反映されない
        for i in range(len(st.session_state.settings_df)):
            st.session_state[f"min_{i}"] = val_min
            st.session_state[f"max_{i}"] = val_max

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

def process_data_with_mapping(raw_df, name_mapping):
    if len(raw_df) > 0:
        first_col = raw_df.iloc[:, 0].astype(str).fillna("")
        comments_data = {}
        has_comment_row = False
        comment_rows = raw_df[first_col.str.contains('コメント', na=False)]
        
        if not comment_rows.empty:
            has_comment_row = True
            c_row_idx = comment_rows.index[-1] 
            for col in raw_df.columns[1:]:
                mapped_col = name_mapping.get(col, col)
                val = raw_df.at[c_row_idx, col]
                if pd.notna(val) and str(val).strip() != "":
                    comments_data[mapped_col] = str(val).strip()
        
        ignore_keywords = ['最終更新日時', 'コメント']
        mask = ~first_col.apply(lambda x: any(x.startswith(k) for k in ignore_keywords))
        clean_df = raw_df[mask].reset_index(drop=True)
        clean_df = clean_df.rename(columns=name_mapping)
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

def solve_shift_schedule(df, min_list, max_list, roster_df=None, fresh_min_list=None, fresh_max_list=None):
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
    
    freshmen_indices = []
    
    if roster_df is not None and '学年' in roster_df.columns:
        member_grade_map = {str(row['氏名']).strip(): str(row['学年']).strip() for _, row in roster_df.iterrows()}
        unique_grades = {g for g in set(member_grade_map.values()) if g and g.lower() != 'nan'}
        
        for m_idx, member in enumerate(members):
            g_str = member_grade_map.get(member, "")
            if g_str == "1" or "1年" in g_str:
                freshmen_indices.append(m_idx)
        
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
        
        if freshmen_indices:
            if fresh_min_list is not None and pd.notna(fresh_min_list[d]):
                f_min = int(fresh_min_list[d])
                prob += pulp.lpSum([x[d, m] for m in freshmen_indices]) >= f_min
            if fresh_max_list is not None and pd.notna(fresh_max_list[d]):
                f_max = int(fresh_max_list[d])
                prob += pulp.lpSum([x[d, m] for m in freshmen_indices]) <= f_max

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
st.write("PCもしくはiPadでの操作をお勧めします。スマートフォンの場合は画面を横向きにすると操作しやすいです。")

# セッション状態
if 'shift_result' not in st.session_state: st.session_state.shift_result = None
if 'editing_member' not in st.session_state: st.session_state.editing_member = None 
if 'editing_date' not in st.session_state: st.session_state.editing_date = None
if 'roster_df' not in st.session_state: st.session_state.roster_df = None
if 'comments_data' not in st.session_state: st.session_state.comments_data = {}
if 'has_comment_row' not in st.session_state: st.session_state.has_comment_row = False
if 'clean_df' not in st.session_state: st.session_state.clean_df = None
if 'raw_df' not in st.session_state: st.session_state.raw_df = None 
if 'name_mappings' not in st.session_state: st.session_state.name_mappings = {} 
if 'mapping_source_selected' not in st.session_state: st.session_state.mapping_source_selected = None 
if 'loaded_resume_name' not in st.session_state: st.session_state.loaded_resume_name = None
if 'confirm_overwrite' not in st.session_state: st.session_state.confirm_overwrite = False
if 'confirm_reset' not in st.session_state: st.session_state.confirm_reset = False
if 'memo_text' not in st.session_state: st.session_state.memo_text = ""

# --- 手順1 (読み込み) ---
st.markdown("### 1. アップロード")

help_text_densuke = """
伝助のCSVファイルのダウンロード方法:
1. 伝助のページの下の方にある「CSV形式でデータを出力する」をクリックする
2. コメントの「出力する」にチェックを入れ、「CSV形式で登録データを出力する」をクリックする
3. 「CSVデータを取得する」をクリックするとダウンロードができる
"""
uploaded_file = st.file_uploader("**伝助のCSVファイル**", type=['csv'], help=help_text_densuke)

# 伝助CSVの処理
if uploaded_file is not None:
    try:
        if 'last_filename' not in st.session_state or st.session_state.last_filename != uploaded_file.name:
            try: raw_df = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                raw_df = pd.read_csv(uploaded_file, encoding='cp932')
            
            cols_str = [str(c) for c in raw_df.columns]
            if '氏名' in cols_str and '学年' in cols_str:
                st.error("エラー：伝助ではなく、部員名簿のCSVファイルがアップロードされた可能性があります。")
            else:
                st.session_state.raw_df = raw_df
                st.session_state.name_mappings = {} 
                
                clean_df, comments_data, has_comment_row = process_data_with_mapping(raw_df, {})
                st.session_state.clean_df = clean_df
                st.session_state.comments_data = comments_data
                st.session_state.has_comment_row = has_comment_row
                st.session_state.last_filename = uploaded_file.name
                st.session_state.shift_result = None
                st.rerun()
            
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {e}")

help_text_roster = """部員名簿のアップロードは以下のメリットがあるため強く推奨します。

・伝助未回答の部員が一目で分かる  
・お稽古を組む際に、同じ日程に同じ学年の部員が入りづらくなる  
・お稽古の部員の名前の順番が、自動で学年順になる  
・部員名簿の3列目にお稽古カウンターが存在する場合、お稽古編集時にそのお稽古カウンターを名前の右に表示できる  

部員名簿の形式について  
一列目:氏名  
二列目:学年  
三列目(任意):付加情報(お稽古カウンター等)  
例: 森下,6(6年生の森下さん)  
山田,4,7(4年生のお稽古カウンターが7回の山田さん)"""

uploaded_roster = st.file_uploader("**(任意) 部員名簿のCSVファイル**", type=['csv'], key="roster", help=help_text_roster)

if uploaded_roster is not None:
    try:
        if 'last_roster_name' not in st.session_state or st.session_state.last_roster_name != uploaded_roster.name:
            try: roster_df = pd.read_csv(uploaded_roster)
            except UnicodeDecodeError:
                uploaded_roster.seek(0)
                roster_df = pd.read_csv(uploaded_roster, encoding='cp932')
            
            if '氏名' not in roster_df.columns:
                st.error("エラー：部員名簿ではなく、伝助のCSVファイルがアップロードされた可能性があります。")
            else:
                st.session_state.roster_df = roster_df
                st.session_state.last_roster_name = uploaded_roster.name
                st.rerun()
    except Exception as e:
        st.error(f"名簿読み込みエラー: {e}")

st.write("")
with st.expander("保存した作業を再開"):
    uploaded_resume = st.file_uploader("**バックアップファイル (.okeiko)**", type=['okeiko'], key="resume_uploader")
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
                st.session_state.raw_df = resume_data.get('raw_df', None)
                st.session_state.name_mappings = resume_data.get('name_mappings', {})
                st.session_state.memo_text = resume_data.get('memo_text', "")
                
                st.session_state.loaded_resume_name = uploaded_resume.name
                st.session_state.confirm_overwrite = False
                st.session_state.confirm_reset = False
                
                st.success("作業データを復元しました。")
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
        st.markdown('<div id="section_settings"></div>', unsafe_allow_html=True)
        st.markdown("### 2. お稽古の人数を設定")
        
        num_absentees = total_members - num_attendees
        st.markdown(f"全<span style='font-weight:bold; font-size:1.2em;'>{total_days}</span>日程　"
                    f"伝助回答者<span style='font-weight:bold; font-size:1.2em;'>{total_members}</span>名　"
                    f"うち参加者<span style='font-weight:bold; font-size:1.2em;'>{num_attendees}</span>名　"
                    f"欠席者<span style='font-weight:bold; font-size:1.2em;'>{num_absentees}</span>名", 
                    unsafe_allow_html=True)
        
        if st.session_state.roster_df is not None:
            r_df = st.session_state.roster_df
            with st.expander("部員の回答状況を表示", expanded=True):
                status_data = []
                densuke_members = clean_df.columns[1:].tolist()
                roster_members_list = [str(n).strip() for n in r_df['氏名'].tolist()]
                
                unknown_in_densuke = sorted([m for m in densuke_members if m not in roster_members_list])
                unanswered_members = sorted([m for m in roster_members_list if m not in densuke_members])
                
                if unknown_in_densuke:
                    st.warning(f"⚠️ 【{len(unknown_in_densuke)}名】 **名簿に登録されていない名前が伝助に見つかりました (表記ゆれの可能性があります):**\n\n{', '.join(unknown_in_densuke)}")
                if unanswered_members:
                    st.error(f"🚨 【{len(unanswered_members)}名】 **未回答者:**\n\n{', '.join(unanswered_members)}")
                
                if unknown_in_densuke and unanswered_members:
                    st.markdown("**🔄 表記ゆれの手動修正 (名前の紐付け)**")
                    st.caption("左側の「伝助の名前」を選択してから、右側の「正しい名前(名簿)」をクリックすると統合されます。")
                    
                    if st.session_state.mapping_source_selected:
                        st.error(f"選択中: **{st.session_state.mapping_source_selected}** → 右側から正しい名前をクリックしてください", icon="✏️")
                    else:
                        st.info("まずは左側から修正したい名前を選んでください 👇")

                    col_map_L, col_map_R = st.columns(2)
                    
                    with col_map_L:
                        st.markdown("###### 伝助のみに存在 (表記ゆれ?)")
                        for unk_name in unknown_in_densuke:
                            label = unk_name
                            if st.session_state.mapping_source_selected == unk_name:
                                label += "\u200b"
                            
                            if st.button(label, key=f"src_{unk_name}", use_container_width=True):
                                if st.session_state.mapping_source_selected == unk_name:
                                    st.session_state.mapping_source_selected = None
                                else:
                                    st.session_state.mapping_source_selected = unk_name
                                st.rerun()

                    with col_map_R:
                        st.markdown("###### 名簿のみに存在 (未回答)")
                        for mis_name in unanswered_members:
                            if st.button(mis_name, key=f"tgt_{mis_name}", use_container_width=True):
                                if st.session_state.mapping_source_selected:
                                    src = st.session_state.mapping_source_selected
                                    st.session_state.name_mappings[src] = mis_name
                                    st.session_state.mapping_source_selected = None
                                    
                                    if st.session_state.raw_df is not None:
                                        clean_df, comments_data, has_comment_row = process_data_with_mapping(st.session_state.raw_df, st.session_state.name_mappings)
                                        st.session_state.clean_df = clean_df
                                        st.session_state.comments_data = comments_data
                                        st.session_state.has_comment_row = has_comment_row
                                        st.session_state.shift_result = None 
                                    st.success(f"{src} を {mis_name} として統合しました")
                                    st.rerun()
                
                if st.session_state.name_mappings:
                    st.markdown("**🔗 現在設定されている紐付け**")
                    for old, new in list(st.session_state.name_mappings.items()):
                        col_btn, col_txt = st.columns([0.6, 5]) 
                        with col_btn:
                            if st.button("解除", key=f"del_map_{old}"):
                                del st.session_state.name_mappings[old]
                                if st.session_state.raw_df is not None:
                                    clean_df, comments_data, has_comment_row = process_data_with_mapping(st.session_state.raw_df, st.session_state.name_mappings)
                                    st.session_state.clean_df = clean_df
                                    st.session_state.comments_data = comments_data
                                    st.session_state.has_comment_row = has_comment_row
                                    st.session_state.shift_result = None
                                st.rerun()
                        with col_txt:
                            st.markdown(f"<div style='line-height: 34px;'>{old} ➡ {new}</div>", unsafe_allow_html=True)

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
                    st.markdown(f"部員名簿(部員数:<span style='font-weight:bold; font-size:1.2em;'>{len(status_data)}</span>名)", unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame(status_data), hide_index=True, use_container_width=True)

        if st.session_state.get('settings_df') is None or len(st.session_state.settings_df) != total_days:
            init_data = {
                "有効": [True] * len(dates_list),
                "日程": dates_list, 
                "最小人数": [default_bulk_min] * len(dates_list), 
                "最大人数": [default_bulk_max] * len(dates_list),
                "1年生最小": [None] * len(dates_list),
                "1年生最大": [None] * len(dates_list)
            }
            st.session_state.settings_df = pd.DataFrame(init_data)
            st.session_state.global_min = default_bulk_min
            st.session_state.global_max = default_bulk_max
        else:
            if "有効" not in st.session_state.settings_df.columns:
                st.session_state.settings_df["有効"] = True
            if "1年生最小" not in st.session_state.settings_df.columns:
                st.session_state.settings_df["1年生最小"] = None
            if "1年生最大" not in st.session_state.settings_df.columns:
                st.session_state.settings_df["1年生最大"] = None
            
            desired_order = ["有効", "日程", "最小人数", "最大人数", "1年生最小", "1年生最大"]
            existing_cols = st.session_state.settings_df.columns.tolist()
            new_order = [c for c in desired_order if c in existing_cols] + [c for c in existing_cols if c not in desired_order]
            st.session_state.settings_df = st.session_state.settings_df[new_order]

        col_min, col_max, col_empty = st.columns([1, 1, 5])
        with col_min:
            if 'global_min' not in st.session_state: st.session_state.global_min = default_bulk_min
            # コールバック関数で個別設定も更新
            st.number_input("最小人数", min_value=0, max_value=safe_input_max, key="global_min", on_change=apply_global_settings)
        with col_max:
            if 'global_max' not in st.session_state: st.session_state.global_max = default_bulk_max
            # コールバック関数で個別設定も更新
            st.number_input("最大人数", min_value=1, max_value=safe_input_max, key="global_max", on_change=apply_global_settings)

        with st.expander("日程ごとの詳細設定", expanded=False):
            st.write("各日程の設定を行います。チェックを外すとその日程はスキップされます。")
            h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([0.5, 2, 1, 1, 1, 1])
            h_col1.markdown("**有効**")
            h_col2.markdown("**日程**")
            h_col3.markdown("**最小**")
            h_col4.markdown("**最大**")
            h_col5.markdown("**1年最小**")
            h_col6.markdown("**1年最大**")
            st.markdown("<hr style='margin: 0px 0px 10px 0px; padding: 0px; border-top: 1px solid rgba(49, 51, 63, 0.2);'>", unsafe_allow_html=True)

            dates = st.session_state.settings_df["日程"].tolist()
            
            updated_enabled = []
            updated_min = []
            updated_max = []
            updated_fmin = []
            updated_fmax = []

            for i, date_val in enumerate(dates):
                c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2, 1, 1, 1, 1])
                
                curr_enabled = bool(st.session_state.settings_df.at[i, "有効"])
                
                # キーの初期値をGlobalから反映するためにsession_stateを確認
                if f"min_{i}" not in st.session_state:
                    st.session_state[f"min_{i}"] = int(st.session_state.settings_df.at[i, "最小人数"])
                if f"max_{i}" not in st.session_state:
                    st.session_state[f"max_{i}"] = int(st.session_state.settings_df.at[i, "最大人数"])
                
                val_fmin = st.session_state.settings_df.at[i, "1年生最小"]
                curr_fmin = int(val_fmin) if pd.notna(val_fmin) else None
                
                val_fmax = st.session_state.settings_df.at[i, "1年生最大"]
                curr_fmax = int(val_fmax) if pd.notna(val_fmax) else None

                new_enabled = c1.checkbox("有効", value=curr_enabled, key=f"en_{i}", label_visibility="collapsed")
                c2.markdown(f"<div style='margin-top: 5px; font-weight:bold;'>{date_val}</div>", unsafe_allow_html=True)
                
                # セッションステートキーを指定することで、Global設定変更時にon_changeで値を書き換えられるようにする
                new_min = c3.number_input("最小", min_value=0, max_value=safe_input_max, key=f"min_{i}", label_visibility="collapsed", disabled=not new_enabled)
                new_max = c4.number_input("最大", min_value=1, max_value=safe_input_max, key=f"max_{i}", label_visibility="collapsed", disabled=not new_enabled)
                
                new_fmin = c5.number_input("1年最小", min_value=0, max_value=safe_input_max, value=curr_fmin, key=f"fmin_{i}", label_visibility="collapsed", placeholder="空", disabled=not new_enabled)
                new_fmax = c6.number_input("1年最大", min_value=0, max_value=safe_input_max, value=curr_fmax, key=f"fmax_{i}", label_visibility="collapsed", placeholder="空", disabled=not new_enabled)

                updated_enabled.append(new_enabled)
                updated_min.append(new_min)
                updated_max.append(new_max)
                updated_fmin.append(new_fmin)
                updated_fmax.append(new_fmax)
            
            # 合計値の表示 (1年生列は空欄)
            st.markdown("<hr style='margin: 10px 0px; padding: 0px; border-top: 1px solid rgba(49, 51, 63, 0.2);'>", unsafe_allow_html=True)
            total_min = sum([m for i, m in enumerate(updated_min) if updated_enabled[i]])
            total_max = sum([m for i, m in enumerate(updated_max) if updated_enabled[i]])

            t1, t2, t3, t4, t5, t6 = st.columns([0.5, 2, 1, 1, 1, 1])
            t2.markdown("**合計** (有効分)")
            t3.markdown(f"**{total_min}**")
            t4.markdown(f"**{total_max}**")
            t5.markdown("")
            t6.markdown("")

        generate_clicked = st.button("🔮 お稽古生成 🔮", type="primary", use_container_width=True)
        
        if generate_clicked:
            st.session_state.settings_df["有効"] = updated_enabled
            st.session_state.settings_df["最小人数"] = updated_min
            st.session_state.settings_df["最大人数"] = updated_max
            st.session_state.settings_df["1年生最小"] = updated_fmin
            st.session_state.settings_df["1年生最大"] = updated_fmax
            
            dates = st.session_state.settings_df["日程"].tolist()
            
            calc_min_l = []
            calc_max_l = []
            calc_fresh_min_l = []
            calc_fresh_max_l = []
            
            for i in range(len(dates)):
                if updated_enabled[i]:
                    calc_min_l.append(updated_min[i])
                    calc_max_l.append(updated_max[i])
                    calc_fresh_min_l.append(updated_fmin[i])
                    calc_fresh_max_l.append(updated_fmax[i])
                else:
                    calc_min_l.append(0)
                    calc_max_l.append(0)
                    calc_fresh_min_l.append(None)
                    calc_fresh_max_l.append(None)

            error_messages = []
            for i, date in enumerate(dates):
                if updated_enabled[i]:
                    if updated_min[i] > updated_max[i]:
                        error_messages.append(f"【{date}】最小人数({updated_min[i]})が最大人数({updated_max[i]})を上回っています。")
                    
                    f_min = updated_fmin[i]
                    f_max = updated_fmax[i]
                    if f_min is not None and f_max is not None:
                        if int(f_min) > int(f_max):
                            error_messages.append(f"【{date}】1年生最小({int(f_min)})が1年生最大({int(f_max)})を上回っています。")
                    
                    if f_min is not None and int(f_min) > updated_max[i]:
                         error_messages.append(f"【{date}】1年生最小({int(f_min)})が最大人数({updated_max[i]})を上回っています。")

            if error_messages:
                for msg in error_messages:
                    st.error(msg)
            else:
                if st.session_state.shift_result is not None:
                    st.session_state.confirm_overwrite = True
                else:
                    st.session_state.confirm_overwrite = False
                    if sum(calc_min_l) > num_attendees: st.warning("※ 設定された最小人数の合計が、出席可能者数を超えています。")
                    with st.spinner('計算中...'):
                        res, success = solve_shift_schedule(clean_df, calc_min_l, calc_max_l, st.session_state.roster_df, calc_fresh_min_l, calc_fresh_max_l)
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
                
                dates = st.session_state.settings_df["日程"].tolist()
                min_l_raw = st.session_state.settings_df["最小人数"].tolist()
                max_l_raw = st.session_state.settings_df["最大人数"].tolist()
                fmin_raw = st.session_state.settings_df["1年生最小"].tolist()
                fmax_raw = st.session_state.settings_df["1年生最大"].tolist()
                enabled_l = st.session_state.settings_df["有効"].tolist()

                calc_min_l = []
                calc_max_l = []
                calc_fresh_min_l = []
                calc_fresh_max_l = []
                
                for i in range(len(dates)):
                    if enabled_l[i]:
                        calc_min_l.append(min_l_raw[i])
                        calc_max_l.append(max_l_raw[i])
                        calc_fresh_min_l.append(fmin_raw[i])
                        calc_fresh_max_l.append(fmax_raw[i])
                    else:
                        calc_min_l.append(0)
                        calc_max_l.append(0)
                        calc_fresh_min_l.append(None)
                        calc_fresh_max_l.append(None)
                
                if sum(calc_min_l) > num_attendees: st.warning("※ 設定された最小人数の合計が、出席可能者数を超えています。")
                with st.spinner('計算中...'):
                    res, success = solve_shift_schedule(clean_df, calc_min_l, calc_max_l, st.session_state.roster_df, calc_fresh_min_l, calc_fresh_max_l)
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
            st.write(""); st.write("---")
            c_head, c_status = st.columns([1, 1.5])
            with c_head: st.subheader("3. 生成されたお稽古を編集")
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
                    st.info("部員または日程をクリックして編集できます")
            
            grade_map = {}
            extra_map = {}
            has_extra_col = False
            col3_name = ""
            
            if st.session_state.roster_df is not None:
                try:
                    for _, r in st.session_state.roster_df.iterrows():
                        grade_map[str(r['氏名']).strip()] = str(r['学年']).strip()
                    
                    if len(st.session_state.roster_df.columns) >= 3:
                        has_extra_col = True
                        col3_name = st.session_state.roster_df.columns[2]
                        for _, r in st.session_state.roster_df.iterrows():
                            val = r[col3_name]
                            if pd.notna(val) and str(val).strip() != "":
                                extra_map[str(r['氏名']).strip()] = str(val).strip()
                except: pass
            
            show_extra_info = False
            if has_extra_col:
                show_extra_info = st.toggle(f"「{col3_name}」を表示する", value=True)

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

            for date_idx, date_val in enumerate(dates_list):
                c_date, c_members = st.columns([1.2, 8], gap="small")
                with c_date:
                    btn_label = f"\u200E{date_val}"
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
                            display_name = member_b
                            if member_b in grade_map: 
                                display_name = f"{grade_map[member_b]}.{member_b}"
                            if show_extra_info and member_b in extra_map:
                                display_name += f"({extra_map[member_b]})"
                            if not is_mem_edit and not is_date_edit and is_locked:
                                lock_label = display_name
                                cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                continue 
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
                                            lock_label = display_name
                                            cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                            continue
                                    elif is_locked:
                                        cols[i].markdown(f"<div class='locked-member'>🔒{display_name}</div>", unsafe_allow_html=True)
                                        continue
                            elif is_date_edit:
                                tgt_date = st.session_state.editing_date
                                if date_val != tgt_date:
                                    stat = get_status(clean_df, tgt_date, member_b)
                                    if stat in ["○", "△"]:
                                        label += "\u200b\u200b"
                                        on_click = "move_to_date"
                                    elif is_locked:
                                        lock_label = display_name
                                        cols[i].markdown(f"<div class='locked-member'>🔒{lock_label}</div>", unsafe_allow_html=True)
                                        continue
                                elif is_locked:
                                    cols[i].markdown(f"<div class='locked-member'>🔒{display_name}</div>", unsafe_allow_html=True)
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
            
            st.write("")
            col_dl_L, col_dl_R = st.columns([3, 1])
            with col_dl_R:
                save_data_temp = {
                    'clean_df': st.session_state.clean_df,
                    'roster_df': st.session_state.roster_df,
                    'shift_result': st.session_state.shift_result,
                    'settings_df': st.session_state.settings_df,
                    'comments_data': st.session_state.comments_data,
                    'has_comment_row': st.session_state.has_comment_row,
                    'memo_text': st.session_state.memo_text
                }
                buffer_temp = io.BytesIO()
                pickle.dump(save_data_temp, buffer_temp)
                today_str = datetime.now().strftime('%Y%m%d')
                file_name_temp = f"{today_str}_backup.okeiko"
                
                st.download_button("💾 作業を保存", data=buffer_temp, file_name=file_name_temp, mime="application/octet-stream", use_container_width=True)

            st.write(""); st.write("")
            st.subheader("お稽古プレビュー")
            st.write("""下のテキストボックスの右上部分をクリックすることで、お稽古のテキストをコピーすることができます。

※(△)について、伝助のコメントを確認し、「遅れ」もしくは「早退」に書き換えた上でご利用ください。""")
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
            
            st.write(""); st.write("")
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
                sorted_densuke_members = sort_members_by_roster(densuke_members, st.session_state.roster_df)
                
                for m in sorted_densuke_members:
                    if m not in assigned_members_set:
                        if m in cm_data:
                            fmt_comment = format_comment_text(cm_data[m])
                            comments_html_lines.append(f"<div style='color: #808080;'>(お休み) {m}：{fmt_comment}</div>")
                
                if comments_html_lines:
                    full_html = "".join(comments_html_lines)
                    st.markdown(f'<div class="comment-container">{full_html}</div>', unsafe_allow_html=True)
                else:
                    st.info("表示すべきコメントはありません")
            
            st.write(""); st.write("")
            st.subheader("メモ")
            st.text_area("自由にメモを残せます", key="memo_text", height=400)
