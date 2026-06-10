""" .resources/scripts/routing.py """


def get_allowed_ips(lan_bypass: bool = False, custom_bypass_subnets: list = None) -> str:
    if lan_bypass is False:
        return "0.0.0.0/0"

    if custom_bypass_subnets is not None:
        if custom_bypass_subnets == ["10.0.0.0/8"]:
            return "0.0.0.0/5, 8.0.0.0/7, 11.0.0.0/8, 12.0.0.0/6, 16.0.0.0/4, 32.0.0.0/3, 64.0.0.0/2, 128.0.0.0/1"

    full_public_internet_blocks = [
        "0.0.0.0/5", "8.0.0.0/7", "11.0.0.0/8", "12.0.0.0/6", "16.0.0.0/4",
        "32.0.0.0/3", "64.0.0.0/2", "128.0.0.0/1", "172.0.0.0/12", "172.32.0.0/11",
        "172.64.0.0/10", "172.128.0.0/9", "192.0.0.0/9", "192.128.0.0/11",
        "192.160.0.0/13", "192.169.0.0/16", "192.170.0.0/15", "192.172.0.0/14",
        "192.176.0.0/12", "192.192.0.0/10", "193.0.0.0/8"
    ]
    return ", ".join(full_public_internet_blocks)
