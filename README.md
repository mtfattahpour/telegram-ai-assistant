# Telegram AI Assistant for Knowledge Synthesis

A Python-based, event-driven tool for filtering and searching Telegram messages, with intelligent summarization and AI-assisted knowledge extraction. Users can query groups or channels in natural language and receive answers based on their content using a special chat inteface in Telegram app.

## Project Motivation

Telegram channels and supergroups are becoming invaluable repositories of information, educational material, case discussions, and shared resources and experiences. However, the sheer volume of messages makes it challenging to extract specific, relevant knowledge efficiently. Standard search functionality implemented by Telegram UI is often insufficient for complex queries, and it is often time-consuming to manually search for the answer to a specific question.

Personally, as an MD graduate, I still access and read Telegram posts and messages from various channels and groups operated by our university (Tehran University of Medical Sciences) and the affiliated research centers and teaching hospitals. This tool aims to leverage the Telethon library and Generative AI to create a powerful knowledge retrieval and synthesis engine, to transform unstructured chat histories into structured, actionable insights.

## Project Vision & Roadmap

This project is under active development. The ultimate goal is to build a feature-rich assistant with the following capabilities:

- **Advanced Search:**
    - Fuzzy string matching for typos and variations.
    - Search based on custom time range, specific sender(s), media attachments.
    - Keyword and regex-based filtering.
    - Retrieval of message chains (a message and all its replies).
- **AI-Powered Functionality:**
    - **Semantic Search:** Find messages based on conceptual meaning, not just keywords.
    - **On-Demand Summarization:** Summarize the last N messages, or an entire discussion, or message chain, on a specific topic.
    - **Query Expansion:** Use AI to suggest related search terms based on an initial query.
- **Data Handling:**
    - Proper parsing and storage of message data (text, sender, date).
    - Future support for handling images and documents.
- **User Interface:**
    - A special chat interface for ease of use; the script will create a new Telegram group, which is the interface for the user to access the features.
- **Agentic Context-Aware Q&A (LLM-Guided Retrieval and Grounded Answering):**
    - Intelligent Knowledge Extraction: Users can query the system with natural language questions (e.g., "What were the consensus treatment protocols discussed last month for pediatric refractory epilepsy?"); The script performs various tasks to acquire and synthesize a response based on the content of the target channel/group in a process that involves iterative context fetching, pagination, non-text attachment handling via heuristics, and returns verifiable citations (including deep links to the messages most pertinent to the query, ...).
    - `--thorough` Mode: An exhaustive search flag that forces the ingestion of massive chat histories (e.g., 5,000+ messages, or large time window) for deep summarization and comprehensive review.
- **Multilingual Support:** Designed for English and RTL languages (specifically Farsi/Persian), utilizing text reshaping and bidi algorithms for accurate processing and display.


## Setup & Installation

1.  **Prerequisites:** Python 3.8+
2.  **Clone the repository:**
    ```bash
    git clone https://github.com/mtfattahpour/telegram-ai-assistant.git
    cd telegram-ai-assistant
    ```
3.  **Create a virtual environment and install dependencies:**
    ```bash
    # Create the environment
    python -m venv .venv
    
    # Activate the environment (Windows)
    .venv\Scripts\activate
    # OR Activate (macOS/Linux)
    source .venv/bin/activate

    pip install -r requirements.txt
    ```
4.  **Obtain Telegram API credentials:**
    * Go to https://my.telegram.org/apps
    * Create an App for `Desktop` and obtain Telegram api_id, api_hash
5.  **Configure API Credentials:**
    * Create a file named `.env` in the root directory.
    * Add your Telegram API credentials to this file:
      ```
      API_ID=1234567
      API_HASH=your_api_hash_here
      ```
6.  **Run the script:**
    ```bash
    python create_session.py
    ```
    * On the first run, you will be prompted to enter your phone number, login code, and two-factor authentication password (if enabled). A `.session` file will be generated, which is a sensitive file that grants programmatic access to the Telegram account and should not be shared with anyone (this session can be terminated from mobile/desktop App at any time).
    * Then run the `main.py` for execution to begin. The script will continue running until Ctrl+C is pressed or a special command `/stop` is sent to the chat inteface.