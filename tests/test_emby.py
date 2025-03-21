from app.emby import Emby

client_emby = Emby()
client_emby.login()
play_state_data = client_emby.Sessions()
play_state_data = client_emby.Sessions()
print(play_state_data)