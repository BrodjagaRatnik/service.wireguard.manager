import sys
import xbmcgui

arg = sys.argv[1].lower() if len(sys.argv) > 1 else "europe"

if arg == "europe":
    title = "NordVPN IDs: Europe"
    codes = (
        "[B][COLOR yellow]EUROPEAN IDs[/COLOR][/B][CR][CR]"
        "Albania: 2 | Andorra: 5 | Austria: 14 | Belgium: 21[CR]"
        "Bosnia/Herz: 27 | Bulgaria: 33 | Croatia: 54 | Cyprus: 56[CR]"
        "Czech Rep: 57 | Denmark: 58 | Estonia: 68 | Finland: 73[CR]"
        "France: 74 | Georgia: 80 | Germany: 81 | Greece: 84[CR]"
        "Hungary: 98 | Iceland: 99 | Ireland: 104 | Italy: 106[CR]"
        "Latvia: 119 | Lithuania: 125 | Luxembourg: 126 | Malta: 134[CR]"
        "Moldova: 142 | Monaco: 143 | Montenegro: 146 | Netherlands: 153[CR]"
        "Norway: 163 | Poland: 174 | Portugal: 175 | Romania: 179[CR]"
        "Serbia: 192 | Slovakia: 196 | Slovenia: 197 | Spain: 202[CR]"
        "Sweden: 208 | Switzerland: 209 | Ukraine: 225 | UK: 227"
    )
elif arg == "americas":
    title = "NordVPN IDs: Americas & Asia"
    codes = (
        "[B][COLOR yellow]AMERICAS & ASIA PACIFIC IDs[/COLOR][/B][CR][CR]"
        "[B]Americas:[/B][CR]"
        "Argentina: 10 | Bahamas: 16 | Belize: 22 | Bermuda: 24[CR]"
        "Bolivia: 26 | Brazil: 30 | Canada: 38 | Chile: 43[CR]"
        "Colombia: 47 | Costa Rica: 52 | Dominican Rep: 61 | Ecuador: 63[CR]"
        "Guatemala: 89 | Honduras: 96 | Mexico: 140 | Panama: 168[CR]"
        "Peru: 171 | Puerto Rico: 176 | USA: 228 | Uruguay: 230[CR][CR]"
        "[B]Asia Pacific:[/B][CR]"
        "Australia: 13 | Hong Kong: 97 | India: 100 | Indonesia: 101[CR]"
        "Japan: 108 | Kazakhstan: 110 | Malaysia: 131 | New Zealand: 156[CR]"
        "Singapore: 195 | South Korea: 114 | Taiwan: 211 | Thailand: 214[CR]"
        "Vietnam: 234"
    )
else:
    title = "NordVPN IDs: Middle East & Africa"
    codes = (
        "[B][COLOR yellow]MIDDLE EAST & AFRICA IDs[/COLOR][/B][CR][CR]"
        "Algeria: 3 | Egypt: 64 | Israel: 105 | Morocco: 147[CR]"
        "South Africa: 200 | Turkey: 220 | UAE: 226[CR]"
        "[CR][I]Note: These regions may have fewer WireGuard servers.[/I]"
    )

xbmcgui.Dialog().textviewer(title, codes)
