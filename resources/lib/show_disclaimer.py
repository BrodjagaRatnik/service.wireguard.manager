import xbmcgui

text = (
    "[B][COLOR yellow]LEGAL DISCLAIMER & TERMS OF USE[/COLOR][/B][CR][CR]"
    "1. [B]Independent Project:[/B] This addon is an independent, community-driven project. "
    "It is NOT affiliated with, authorized, or endorsed by NordVPN, Nord Security, or its "
    "affiliates. 'NordVPN' and 'NordLynx' are trademarks of Nord Security.[CR][CR]"
    
    "2. [B]No Warranty:[/B] This software is provided 'AS IS' without any warranty. "
    "The developer is not responsible for any loss of data, hardware damage (including "
    "Raspberry Pi 5 thermal or power issues), or network vulnerabilities resulting "
    "from the use of this script.[CR][CR]"
    
    "3. [B]Security Risk:[/B] Handling WireGuard private keys and NordVPN tokens through "
    "third-party scripts carries inherent security risks. Users are solely responsible "
    "for verifying the safety of their own connection and account credentials.[CR][CR]"
    
    "4. [B]Compliance:[/B] It is the user's responsibility to ensure that using this "
    "tool does not violate the NordVPN Terms of Service or local laws regarding "
    "VPN usage.[CR][CR]"
    
    "[I]By using this manager, you acknowledge that you have read and agree to "
    "these terms.[/I]"
)

xbmcgui.Dialog().ok("WireGuard Manager: Legal Notice", text)
