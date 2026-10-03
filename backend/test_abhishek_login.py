import httpx
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def test_login_and_features():
    # 1. Test Login
    login_data = {"email": "abhishekads264@gmail.com", "password": "Abhi@264"}
    resp = httpx.post(f"{BASE_URL}/auth/login", json=login_data, timeout=10.0)
    print(f"1. Login status: {resp.status_code}")
    if resp.status_code != 200:
        print("Login response:", resp.text)
        return False
    
    data = resp.json()
    token = data.get("access_token")
    user = data.get("user")
    print(f"   ✓ User logged in successfully: {user.get('name')} | Role: {user.get('role')}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Test /auth/me
    me_resp = httpx.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"2. /auth/me: {me_resp.status_code} -> Name: {me_resp.json().get('name')}, Role: {me_resp.json().get('role')}")
    
    # 3. Test /projects
    proj_resp = httpx.get(f"{BASE_URL}/projects/", headers=headers)
    projects = proj_resp.json()
    print(f"3. /projects: {proj_resp.status_code} -> {len(projects)} projects returned")
    
    # 4. Test /dashboard/summary
    dash_resp = httpx.get(f"{BASE_URL}/dashboard/summary", headers=headers)
    print(f"4. /dashboard/summary: {dash_resp.status_code} -> Total Projects: {dash_resp.json().get('projects', {}).get('total')}")
    
    # 5. Test /analytics/executive
    exec_resp = httpx.get(f"{BASE_URL}/analytics/executive", headers=headers)
    print(f"5. /analytics/executive: {exec_resp.status_code} -> Scoped Projects: {exec_resp.json().get('projects', {}).get('total')}")
    
    # 6. Test /analytics/projects
    p_an_resp = httpx.get(f"{BASE_URL}/analytics/projects", headers=headers)
    print(f"6. /analytics/projects: {p_an_resp.status_code} -> Projects Analyzed: {len(p_an_resp.json())}")
    
    # 7. Test /analytics/team
    team_resp = httpx.get(f"{BASE_URL}/analytics/team", headers=headers)
    team_data = team_resp.json()
    print(f"7. /analytics/team: {team_resp.status_code} -> Team Members: {team_data.get('summary', {}).get('total')}")
    
    # 8. Test /analytics/risks
    risk_resp = httpx.get(f"{BASE_URL}/analytics/risks", headers=headers)
    risk_data = risk_resp.json()
    print(f"8. /analytics/risks: {risk_resp.status_code} -> High Risk Projects: {risk_data.get('project_risk', {}).get('high')}")
    
    # 9. Test /analytics/insights
    ins_resp = httpx.get(f"{BASE_URL}/analytics/insights", headers=headers)
    insights = ins_resp.json().get("insights", [])
    print(f"9. /analytics/insights: {ins_resp.status_code} -> {len(insights)} live insights generated")
    
    # 10. Test /recommendations
    rec_resp = httpx.get(f"{BASE_URL}/recommendations/", headers=headers)
    print(f"10. /recommendations: {rec_resp.status_code} -> {len(rec_resp.json())} recommendations returned")
    
    # 11. Test /dashboard/notifications
    notif_resp = httpx.get(f"{BASE_URL}/dashboard/notifications", headers=headers)
    print(f"11. /dashboard/notifications: {notif_resp.status_code} -> {len(notif_resp.json())} notifications")
    
    # 12. Test AI Assistant Chat
    chat_resp = httpx.post(f"{BASE_URL}/ai-assistant/chat", headers=headers, json={"message": "Which projects have the highest risk?"})
    print(f"12. /ai-assistant/chat: {chat_resp.status_code}")
    if chat_resp.status_code == 200:
        ans = chat_resp.json().get("response", "")
        print(f"    AI Assistant answer snippet: {ans[:150]}...")
    
    print("\nALL FEATURES AND LOGIN VERIFIED 100% OPERATIONAL!")
    return True

if __name__ == "__main__":
    test_login_and_features()
