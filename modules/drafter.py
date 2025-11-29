import streamlit as st
from datetime import datetime

def render_drafter(page_type="question"):
    """Render the Legislative Drafter interface"""
    
    st.markdown("## 📝 Legislative Drafter")
    st.markdown("**The Writing Engine** - Generate parliamentary questions and zero hour speeches")
    st.markdown("---")
    
    # Create tabs for both functionalities
    tab1, tab2 = st.tabs(["📋 Parliamentary Question Generator", "⏰ Zero Hour Drafter"])
    
    # Tab 1: Parliamentary Question Generator
    with tab1:
        render_question_generator()
    
    # Tab 2: Zero Hour Drafter
    with tab2:
        render_zero_hour_drafter()

def render_question_generator():
    """Render the Parliamentary Question Generator"""
    
    st.subheader("📋 Parliamentary Question Generator")
    st.markdown("Generate questions in the **Lok Sabha format**")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        topic = st.text_area(
            "Question Topic",
            placeholder="e.g., Implementation of Digital India program in rural areas",
            height=100,
            help="Enter the main topic or subject of your parliamentary question"
        )
    
    with col2:
        ministry = st.selectbox(
            "Ministry",
            [
                "Agriculture and Farmers Welfare",
                "Civil Aviation",
                "Commerce and Industry",
                "Communications",
                "Culture",
                "Defence",
                "Electronics and Information Technology",
                "Environment, Forest and Climate Change",
                "External Affairs",
                "Finance",
                "Health and Family Welfare",
                "Home Affairs",
                "Housing and Urban Affairs",
                "Human Resource Development",
                "Labour and Employment",
                "Law and Justice",
                "Micro, Small and Medium Enterprises",
                "Minority Affairs",
                "Power",
                "Railways",
                "Road Transport and Highways",
                "Rural Development",
                "Science and Technology",
                "Shipping",
                "Skill Development and Entrepreneurship",
                "Social Justice and Empowerment",
                "Statistics and Programme Implementation",
                "Textiles",
                "Tourism",
                "Water Resources, River Development and Ganga Rejuvenation",
                "Women and Child Development",
                "Youth Affairs and Sports"
            ],
            help="Select the relevant ministry for this question"
        )
        
        question_type = st.radio(
            "Question Type",
            ["Starred", "Unstarred"],
            horizontal=True,
            help="Starred questions require oral answers, Unstarred questions require written answers"
        )
    
    if st.button("🎯 Generate Question", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("❌ Please enter a topic for the question.")
        else:
            # Generate the question in Lok Sabha format
            generated_question = generate_parliamentary_question(topic, ministry, question_type)
            
            st.success("✅ Question generated successfully!")
            st.markdown("---")
            st.markdown("### 📄 Generated Parliamentary Question")
            
            # Display in a formatted box
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #002D62;">
                <p style="margin: 0; white-space: pre-line;">{generated_question}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Download button
            st.download_button(
                label="📥 Download Question",
                data=generated_question,
                file_name=f"parliamentary_question_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

def render_zero_hour_drafter():
    """Render the Zero Hour Drafter"""
    
    st.subheader("⏰ Zero Hour Drafter")
    st.markdown("Draft urgent matters for **Zero Hour** in Lok Sabha")
    st.markdown("---")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        urgent_issue = st.text_area(
            "Urgent Issue",
            placeholder="e.g., Water crisis affecting farmers in Maharashtra",
            height=120,
            help="Describe the urgent issue that needs to be raised"
        )
    
    with col2:
        severity = st.select_slider(
            "Severity Level",
            options=["Medium", "High"],
            value="High",
            help="Select the severity level of the issue"
        )
        
        constituency = st.text_input(
            "Constituency (Optional)",
            placeholder="e.g., Mumbai South",
            help="Your constituency name"
        )
    
    if st.button("🎯 Generate Speech", type="primary", use_container_width=True):
        if not urgent_issue.strip():
            st.error("❌ Please enter an urgent issue to raise.")
        else:
            # Generate the zero hour speech
            generated_speech = generate_zero_hour_speech(urgent_issue, severity, constituency)
            
            st.success("✅ Speech drafted successfully!")
            st.markdown("---")
            st.markdown("### 🎤 Generated Zero Hour Speech")
            
            # Display in a formatted box
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #002D62;">
                <p style="margin: 0; white-space: pre-line; line-height: 1.6;">{generated_speech}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Word count
            word_count = len(generated_speech.split())
            st.info(f"📊 Word Count: {word_count} words")
            
            # Download button
            st.download_button(
                label="📥 Download Speech",
                data=generated_speech,
                file_name=f"zero_hour_speech_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

def generate_parliamentary_question(topic: str, ministry: str, question_type: str) -> str:
    """Generate a parliamentary question in Lok Sabha format"""
    
    question_number = "*" if question_type == "Starred" else ""
    
    question = f"""{'*' if question_type == 'Starred' else ''}QUESTION NO. ____

({question_type.upper()})

Will the Minister of {ministry} be pleased to state:

(a) Whether the Government has noted the matter regarding {topic};

(b) If so, the details thereof along with the current status of the issue;

(c) The steps taken or proposed to be taken by the Government in this regard;

(d) The funds allocated for addressing this matter and the timeline for implementation; and

(e) Whether any assessment has been made regarding the impact on the affected population, if so, the details thereof?

---

Date: {datetime.now().strftime('%d %B, %Y')}
Type: {question_type} Question
Ministry: {ministry}
"""
    
    return question

def generate_zero_hour_speech(issue: str, severity: str, constituency: str = "") -> str:
    """Generate a Zero Hour speech script"""
    
    constituency_text = f" and particularly the people of {constituency}" if constituency else ""
    
    severity_phrases = {
        "High": "extremely urgent and critical",
        "Medium": "urgent and significant"
    }
    
    speech = f"""Hon'ble Speaker Sir,

I rise to raise a matter of {severity_phrases.get(severity, 'urgent')} public importance regarding {issue}.

This matter is of grave concern to the people of my constituency{constituency_text}. The situation demands immediate attention and intervention from the Government.

The issue at hand has been affecting the daily lives of countless citizens, causing significant hardship and distress. Despite repeated representations, the matter remains unaddressed, leading to growing frustration among the affected population.

I urge the Government to take immediate cognizance of this situation and implement necessary measures to provide relief to the affected people. The delay in action is causing irreparable damage and undermining public trust in our institutions.

Through you, Sir, I request the concerned Ministry to:

1. Conduct an immediate assessment of the situation on the ground
2. Allocate necessary resources and funds to address the issue
3. Set up a time-bound action plan with clear milestones
4. Ensure regular monitoring and reporting of the progress
5. Provide interim relief measures to the affected population

I also request that a detailed statement be laid on the Table of the House regarding the steps taken and the timeline for resolution of this matter.

Sir, this is not just about policy or administration—it is about the lives and livelihoods of our people who look to us for solutions. I hope the Government will rise to the occasion and take swift action.

Thank you, Sir.

---

Date: {datetime.now().strftime('%d %B, %Y')}
Severity: {severity}
{f'Constituency: {constituency}' if constituency else ''}
"""
    
    return speech
