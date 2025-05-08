import requests
import json

# Your Discord Webhook URL
WEBHOOK_URL = ""

# Embed Data
embed = {
    "title": "🚨 Global Ban Guidelines 🚨",
    "description": (
        "The **Global Ban** command should only be used in severe cases where a user poses a threat "
        "to multiple servers. It must not be used for minor infractions or personal disagreements."
    ),
    "color": 16711680,  # Red Color
    "fields": [
        {
            "name": "⚠️ **Automatic Global Ban Offenses**",
            "value": (
                "- **Severe Harassment or Threats** (Doxxing, death threats, targeted harassment)\n"
                "- **Hate Speech & Discrimination** (Racism, sexism, homophobia, etc.)\n"
                "- **Severe NSFW Content** (Illegal content, explicit material, disturbing imagery)\n"
                "- **Severe Scamming or Phishing** (Account theft, malware, financial deception)\n"
                "- **Impersonation of Staff/Admins** (Fake identities to manipulate users)\n"
                "- **Mass Server Disruption** (Raiding, bot spam, mass trolling)"
            ),
            "inline": False
        },
        {
            "name": "🛑 **Discretionary Global Ban Offenses**",
            "value": (
                "- **Repeated Violations Across Servers** (Ongoing serious infractions)\n"
                "- **Evading Previous Bans** (Creating multiple accounts to bypass bans)\n"
                "- **Encouraging or Coordinating Toxicity** (Causing drama or misinformation)\n"
                "- **Severe Advertising Spam** (Mass advertising despite warnings)"
            ),
            "inline": False
        },
        {
            "name": "🚫 **When NOT to Use Global Ban**",
            "value": (
                "- **Personal Disputes** (Disagreements that do not affect the community)\n"
                "- **Mild Toxicity** (Arguments, light trolling, occasional rudeness)\n"
                "- **First-Time Offenses** (Unless extreme, local bans should be considered first)\n"
                "- **Minor Rule Violations** (Small infractions that do not justify a global ban)"
            ),
            "inline": False
        },
        {
            "name": "📜 **Ban Process & Documentation**",
            "value": (
                "- **📝 Evidence Required** (Screenshots, logs, or proof before banning)\n"
                "- **📂 Report in Admin Log** (Every global ban must be logged, including reasons & evidence)"
            ),
            "inline": False
        }
    ],
    "footer": {
        "text": "Use the Global Ban command responsibly. Only ban users who are a genuine threat across servers."
    }
}

# Webhook Payload
data = {
    "username": "Global Rules",
    "avatar_url": "https://cdn-icons-png.flaticon.com/512/616/616489.png",  # Example moderation icon
    "embeds": [embed]
}

# Send the request
response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers={"Content-Type": "application/json"})

# Check response
if response.status_code == 204:
    print("✅ Embed sent successfully!")
else:
    print(f"❌ Failed to send embed. HTTP Status: {response.status_code}")
    print(response.text)