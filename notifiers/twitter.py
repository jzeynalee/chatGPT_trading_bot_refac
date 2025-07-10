import tweepy

class TwitterNotifier:
    
    def __init__(self, api_key, api_secret, access_token, access_secret):
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        self.api = tweepy.API(auth)

    def send_message(self, text):
        try:
            self.api.update_status(status=text)
        except Exception as e:
            print(f"[Twitter Error] {e}")
