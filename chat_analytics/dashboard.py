import streamlit as st
import pandas as pd
import altair as alt
from time import sleep
from datetime import datetime, timedelta
from sqlalchemy import func, select, text
from db import get_db_engine, UnifiedChats, ChatSource, SenderType, AppConfig, get_session

# Page Config
st.set_page_config(
    page_title="Chat Analytics",
    page_icon="📊",
    layout="wide"
)

@st.cache_data(ttl=60)
def load_data():
    engine = get_db_engine()
    
    with engine.connect() as conn:
        # User Messages Count
        total_user_msgs = conn.execute(
            select(func.count(UnifiedChats.id)).where(UnifiedChats.sender_type == SenderType.USER.name)
        ).scalar()
        
        # Recent
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_user_msgs = conn.execute(
            select(func.count(UnifiedChats.id)).where(
                UnifiedChats.timestamp >= yesterday,
                UnifiedChats.sender_type == SenderType.USER.name
            )
        ).scalar()
        
        # Negative %
        total_analyzed = conn.execute(
            select(func.count(UnifiedChats.id)).where(
                UnifiedChats.is_analyzed == True,
                UnifiedChats.sender_type == SenderType.USER.name
            )
        ).scalar()
        
        neg_count = conn.execute(
            select(func.count(UnifiedChats.id)).where(
                UnifiedChats.sentiment == 'negative',
                UnifiedChats.sender_type == SenderType.USER.name
            )
        ).scalar()
        
        neg_pct = 0.0
        if total_analyzed and total_analyzed > 0:
            neg_pct = (neg_count / total_analyzed) * 100
            
        # Top Topics
        top_topics_query = """
            SELECT topic, COUNT(*) as count 
            FROM unified_chats 
            WHERE is_analyzed = TRUE AND topic != 'unknown' AND sender_type = 'USER'
            GROUP BY topic 
            ORDER BY count DESC 
            LIMIT 5
        """
        top_topics_df = pd.read_sql(top_topics_query, conn)
        
        # Timeline (Daily)
        if engine.dialect.name == 'sqlite':
            date_col = func.strftime('%Y-%m-%d', UnifiedChats.timestamp)
        else:
            date_col = func.date_trunc('day', UnifiedChats.timestamp)

        stmt = (
            select(
                date_col.label('day'),
                UnifiedChats.source,
                func.count(UnifiedChats.id).label('count')
            )
            .where(
                UnifiedChats.timestamp.isnot(None),
                UnifiedChats.sender_type == SenderType.USER.name
            )
            .group_by('day', UnifiedChats.source)
            .order_by('day')
        )
        timeline_df = pd.read_sql(stmt, conn)
        
        # Ensure correct types for Charting
        if not timeline_df.empty:
            if 'source' in timeline_df.columns:
                 timeline_df['source'] = timeline_df['source'].apply(lambda x: x.name if hasattr(x, 'name') else str(x))
            # Convert 'day' to datetime for proper Altair temporal scaling
            timeline_df['day'] = pd.to_datetime(timeline_df['day'])

        # Peak Hours Analysis
        peak_query = text("""
            SELECT 
                CASE WHEN STRFTIME('%H', timestamp) IS NOT NULL THEN STRFTIME('%H', timestamp) ELSE '00' END as hour,
                COUNT(*) as count
            FROM unified_chats
            WHERE sender_type = 'USER'
            GROUP BY hour
            ORDER BY hour
        """) if engine.dialect.name == 'sqlite' else text("""
            SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
            FROM unified_chats
            WHERE sender_type = 'USER'
            GROUP BY hour
            ORDER BY hour
        """)
        peak_df = pd.read_sql(peak_query, conn)
        
        # Format Hour for readability (00 -> 12 AM)
        if not peak_df.empty:
            # Ensure hour string is converted to int for sorting
            peak_df['hour_int'] = peak_df['hour'].astype(int)
            # Create readable label
            peak_df['hour_label'] = peak_df['hour_int'].apply(
                lambda x: datetime.strptime(str(x), "%H").strftime("%I %p").lstrip("0")
            )

    return {
        "total": total_user_msgs,
        "recent": recent_user_msgs,
        "neg_pct": neg_pct,
        "top_topics": top_topics_df,
        "timeline": timeline_df,
        "peak_hours": peak_df
    }

def update_email_setting(new_email):
    session = get_session()
    try:
        config = session.query(AppConfig).filter_by(key="alert_email").first()
        if not config:
            config = AppConfig(key="alert_email", value=new_email)
            session.add(config)
        else:
            config.value = new_email
        session.commit()
        return True
    except Exception as e:
        return False
    finally:
        session.close()

def get_current_email():
    session = get_session()
    email = ""
    try:
        config = session.query(AppConfig).filter_by(key="alert_email").first()
        if config:
            email = config.value
    except:
        pass
    finally:
        session.close()
    return email

def main():
    # Header Section
    col_title, col_refresh = st.columns([4, 1])
    
    with col_title:
        st.title("Chat Analytics Dashboard")
        
    with col_refresh:
        st.write("") # Spacer to align button
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            with st.spinner("Reloading..."):
                st.cache_data.clear()
                sleep(0.5)
                st.rerun()

    # Tabs Layout
    tab1, tab2, tab3 = st.tabs(["Overview", "Deep Dive", "Settings"])
    
    data = load_data()

    with tab1:
        # Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total User Messages", f"{data['total']:,}")
        col2.metric("New (24h)", f"{data['recent']:,}")
        col3.metric("Negative Sentiment Rate", f"{data['neg_pct']:.1f}%")
        
        st.divider()
        
        # Timeline Chart
        st.subheader("Daily Message Volume")
        if not data['timeline'].empty:
            chart = alt.Chart(data['timeline']).mark_line(point=True, color='black').encode(
                x=alt.X('day:T', axis=alt.Axis(format='%b %d', labelAngle=-45, title='Date')),
                y=alt.Y('count:Q', title='Messages Count'),
                color=alt.Color('source:N', scale=alt.Scale(range=['#333333', '#888888'])),
                tooltip=[alt.Tooltip('day:T', format='%Y-%m-%d'), 'source', 'count']
            ).properties(
                height=350
            ).interactive(bind_y=False) # Only bind X-Axis (Time) to Zoom/Pan
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No timeline data available.")

    with tab2:
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Discussion Topics")
            if not data['top_topics'].empty:
                bar = alt.Chart(data['top_topics']).mark_bar(color='#444444').encode(
                    x=alt.X('count:Q', title='Volume'),
                    y=alt.Y('topic:N', sort='-x', title='Topic'),
                    tooltip=['topic', 'count']
                ).properties(height=300)
                st.altair_chart(bar, use_container_width=True)
        
        with c2:
            st.subheader("Peak Activity Hours (UTC)")
            if not data['peak_hours'].empty:
                peak_chart = alt.Chart(data['peak_hours']).mark_bar(color='#999999').encode(
                    x=alt.X('hour_label:N', title='Hour', sort=alt.EncodingSortField(field="hour_int", order="ascending")),
                    y=alt.Y('count:Q', title='Messages'),
                    tooltip=[alt.Tooltip('hour_label', title='Hour'), 'count']
                ).properties(height=300)
                st.altair_chart(peak_chart, use_container_width=True)

        st.divider()
        st.subheader("Message Inspector")
        engine = get_db_engine()
        # Search
        col_search, col_space = st.columns([1, 2])
        with col_search:
            search_term = st.text_input("Filter by Keyword", placeholder="e.g. rent, price...")
        
        query = "SELECT timestamp, phone_number, sentiment, topic, message_text FROM unified_chats WHERE sender_type = 'USER'"
        if search_term:
            query += f" AND message_text LIKE '%%{search_term}%%'"
        
        query += " ORDER BY timestamp DESC LIMIT 50"
        
        try:
            df = pd.read_sql(query, engine)
            st.dataframe(df, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Search error (check quotes?): {e}")

    with tab3:
        st.header("Configuration")
        st.info("Manage system settings here.")
        
        with st.expander("🔔 Alert Settings", expanded=True):
            current_email = get_current_email()
            with st.form("email_form"):
                new_email = st.text_input("Alert Email Recipient", value=current_email, help="Who should receive pipeline alerts?")
                submitted = st.form_submit_button("Save Changes")
                if submitted:
                    if update_email_setting(new_email):
                        st.success(f"Updated alert email to: {new_email}")
                    else:
                        st.error("Failed to update settings. Check logs.")

if __name__ == "__main__":
    main()
