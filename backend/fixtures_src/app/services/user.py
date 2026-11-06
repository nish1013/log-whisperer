def get_profile(user):
    return {"name": user["name"], "email": user["email"]}


def show_profile():
    return get_profile({"id": 7, "name": "Ana"})
