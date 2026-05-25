# No API Key AI Assistant

This is a Streamlit AI-style assistant that does not require an OpenAI API key, Claude API key, Gemini API key, or billing account.

## Important Limitation

This app does not use a real large language model API. Because of that, it will not be as powerful as Claude or ChatGPT.

It can still help with:

- General questions using Wikipedia lookup
- Basic construction/geotechnical definitions
- Math calculations
- Simple summaries
- Email drafts
- Checklists

## Files

```text
app.py
requirements.txt
runtime.txt
README.md
.gitignore
```

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Upload these files to your GitHub repository root.
2. Go to Streamlit Cloud.
3. Create or update your app.
4. Set the main file path to:

```text
app.py
```

5. Reboot the app.

No secrets are required.
