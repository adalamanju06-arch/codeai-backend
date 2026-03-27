import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Supabase
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

def fetch_github_content(repo_url):
    """Simple scraper to grab the README of a public repo to give the AI context."""
    # Convert https://github.com/user/repo to API URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        user, repo = parts[-2], parts[-1]
        api_url = f"https://api.github.com/repos/{user}/{repo}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return response.text
    return "No README or codebase context found."

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_query = data.get('query')
    github_url = data.get('github_url', '')

    # 1. Fetch GitHub Context
    code_context = ""
    if github_url:
        code_context = fetch_github_content(github_url)

    # 2. Call OpenRouter (Using a free model)
    system_prompt = "You are TalkToCode, an AI senior dev guru. Explain code and solve issues."
    full_prompt = f"Context from repository:\n{code_context[:3000]}\n\nUser Question: {user_query}"

    openrouter_response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://your-frontend-url.com",
            "Content-Type": "application/json"
        },
        json={
            "model": "meta-llama/llama-3-8b-instruct:free", # Free model
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ]
        }
    )
    
    ai_text = "Error communicating with AI."
    if openrouter_response.status_code == 200:
        ai_text = openrouter_response.json()['choices'][0]['message']['content']

    # 3. Save to Supabase
    supabase.table('user_queries').insert({
        "github_url": github_url,
        "query": user_query,
        "ai_response": ai_text
    }).execute()

    return jsonify({"response": ai_text})

if __name__ == '__main__':
    app.run(debug=True, port=5000)