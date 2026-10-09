""" ./resources/scripts/dnsleaktest.py """
import json
import os
import socket
import sys
import time
import urllib.request

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'lib'))
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

API_DOMAIN = 'bash.ws'


def main():
    from logger import log_message
    from dialog import TaskProgress, show_ok

    progress = TaskProgress("DNS Leak Test", "Preparing DNS leak test...")
    log_message("DNS Leak Test: Initializing connectivity check", 0)

    try:
        if progress.iscanceled():
            log_message("DNS Leak Test: User aborted before connectivity check.", 0)
            return

        progress.update(5, "Checking connection...")
        try:
            req = urllib.request.Request(f"https://{API_DOMAIN}", method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    log_message("DNS Leak Test: Host unreachable", 3)
                    progress.update(100, "Service unreachable")
                    show_ok("[B]DNS Test[/B]", "[COLOR FFFF0000]Test service unreachable. Try again later.[/COLOR]")
                    return
        except Exception as conn_fault:
            log_message(f"DNS Leak Test: Connectivity failed: {conn_fault}", 3)
            progress.update(100, "Connection failed")
            show_ok("[B]DNS Test[/B]", "[COLOR FFFF0000]No VPN connection available.[/COLOR]")
            return

        if progress.iscanceled():
            log_message("DNS Leak Test: User aborted before session allocation.", 0)
            return

        progress.update(15, "Generating test session...")
        try:
            with urllib.request.urlopen(f"https://{API_DOMAIN}/id", timeout=5) as resp:
                test_id = resp.read().decode('utf-8').strip()
        except Exception as id_fault:
            log_message(f"DNS Leak Test: ID generation failed: {id_fault}", 3)
            return

        log_message(f"DNS Leak Test: Session ID allocated: {test_id}", 0)

        total_probes = 10
        for probe_index in range(1, total_probes + 1):
            if progress.iscanceled():
                log_message("DNS Leak Test: User aborted during resolver probing.", 0)
                return
            probe_percent = 20 + int((probe_index / total_probes) * 50)
            progress.update(probe_percent, f"Sending resolver probe {probe_index}/{total_probes}...")
            target_host = f"{probe_index}.{test_id}.{API_DOMAIN}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(b"\x00", (target_host, 53))
                sock.close()
            except Exception:
                pass
            time.sleep(0.05)

        if progress.iscanceled():
            log_message("DNS Leak Test: User aborted before payload retrieval.", 0)
            return

        progress.update(75, "Collecting resolver responses...")
        try:
            with urllib.request.urlopen(f"https://{API_DOMAIN}/dnsleak/test/{test_id}?json", timeout=8) as resp:
                server_data = json.loads(resp.read().decode('utf-8').strip())
        except Exception as payload_fault:
            log_message(f"DNS Leak Test: Failed fetching payload: {payload_fault}", 3)
            return

        progress.update(90, "Analyzing results...")

        detected_ip = "Unknown"
        dns_servers = []
        conclusion = "Unknown"

        for entry in server_data:
            etype = entry.get("type", "")
            ip_val = entry.get("ip", "").strip()
            country = entry.get("country_name", "").strip()

            if not ip_val:
                continue

            detail = f" [{country}]" if country and country != "false" else ""
            formatted = f"{ip_val}{detail}"

            if etype == "ip":
                detected_ip = formatted
            elif etype == "dns":
                dns_servers.append(formatted)
            elif etype == "conclusion":
                conclusion = entry.get("ip", "")

        progress.update(100, "Test complete")

        log_message(
            f"DNS Leak Test Results - IP: {detected_ip} | DNS Count: {len(dns_servers)} | Conclusion: {conclusion}",
            1
        )

        title = "[B]≡ DNS LEAK TEST RESULTS ≡[/B]"
        msg = f"[COLOR FFFFFF00]Your Public IP:[/COLOR]\n{detected_ip}\n"

        if not dns_servers:
            msg += "[COLOR FFFF0000]No DNS Servers detected![/COLOR]\n"
        else:
            msg += f"[COLOR FFFFFF00]Detected DNS ({len(dns_servers)}):[/COLOR]\n"
            msg += "\n".join(dns_servers[:3])
            if len(dns_servers) > 3:
                msg += f" And {len(dns_servers) - 3} more..."
            msg += "\n"

        if "is leaking" in conclusion.lower():
            msg += f"[COLOR FFFF0000]Conclusion: {conclusion}[/COLOR]"
        else:
            msg += f"[COLOR FF00FF00]Conclusion: {conclusion}[/COLOR]"

        show_ok(title, msg)

    finally:
        progress.close()


if __name__ == "__main__":
    main()
