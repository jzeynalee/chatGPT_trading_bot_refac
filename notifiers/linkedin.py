class LinkedInNotifier:
    def __init__(self, access_token):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }

    def send_post(self, message):
        url = "https://api.linkedin.com/v2/ugcPosts"
        payload = {
            "author": "urn:li:person:YOUR_PROFILE_ID",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": message},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            print("✅ LinkedIn post sent.")
        except Exception as e:
            print(f"❌ LinkedIn error: {e}")
