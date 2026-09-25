"""Fictional development data for Nexa. Every person, team and incident is invented."""

from __future__ import annotations

TEAMS = [
    ("IT Support", "Service desk: accounts, devices, everyday requests.", True),
    ("Network", "VPN, Wi-Fi, connectivity and DNS.", False),
    ("Security", "Identity, certificates, phishing and incident response.", False),
    ("Infrastructure", "Servers, cloud, deployment platform and databases.", False),
    ("Applications", "Business applications, email and collaboration tools.", False),
]

SERVICES = [
    # name, description, category, owner team, criticality
    ("VPN", "Remote access to the corporate network (AnyConnect).", "Network", "Network", "high"),
    ("Corporate Wi-Fi", "Corp-Secure (802.1X) and guest wireless networks.", "Network", "Network", "medium"),
    ("Identity & SSO", "Single sign-on, MFA and directory accounts.", "Access", "Security", "critical"),
    ("Email & Calendar", "Mail, calendar and mobile sync.", "Email & Collaboration", "Applications", "high"),
    ("Laptops & Endpoints", "Company laptops, MDM enrolment and peripherals.", "Hardware", "IT Support", "medium"),
    ("Deployment Pipeline", "CI/CD and production deployment system.", "Infrastructure", "Infrastructure", "critical"),
]

RULES = [
    # name, category, subcategory, team, level, order
    ("VPN issues → Network", "Network", "VPN", "Network", "L1", 10),
    ("Network (other) → Network", "Network", None, "Network", "L1", 50),
    ("Password resets → IT Support", "Access", "Password Reset", "IT Support", "L1", 10),
    ("MFA → IT Support", "Access", "MFA", "IT Support", "L1", 10),
    ("Account lockout → IT Support", "Access", "Account Lockout", "IT Support", "L1", 10),
    ("Production access → Applications", "Access", "Production Access", "Applications", "L1", 10),
    ("SSO → Security", "Access", "SSO", "Security", "L1", 20),
    ("Security incidents → Security", "Security", None, "Security", "L1", 50),
    ("Email & collaboration → Applications", "Email & Collaboration", None, "Applications", "L1", 50),
    ("Hardware → IT Support", "Hardware", None, "IT Support", "L1", 50),
    ("Software → Applications", "Software", None, "Applications", "L1", 60),
    ("Infrastructure → Infrastructure", "Infrastructure", None, "Infrastructure", "L1", 50),
]

# key, name, email local part, role, level, team, job title, department, location
USERS = [
    ("admin", "Jordan Blake", "jordan.blake", "admin", None, "IT Support", "IT Operations Lead", "IT", "London HQ"),
    ("rahul", "Rahul Sharma", "rahul.sharma", "engineer", "L1", "Network", "Network Support Engineer", "IT", "London HQ"),
    ("daniel", "Daniel Okafor", "daniel.okafor", "engineer", "L2", "Network", "Senior Network Engineer", "IT", "London HQ"),
    ("sarah", "Sarah Lin", "sarah.lin", "engineer", "L1", "IT Support", "Service Desk Engineer", "IT", "New York"),
    ("priya", "Priya Nair", "priya.nair", "engineer", "L1", "Applications", "Applications Support Engineer", "IT", "Bengaluru"),
    ("marcus", "Marcus Chen", "marcus.chen", "engineer", "L2", "Applications", "Senior Platform Engineer", "IT", "Berlin"),
    ("aisha", "Aisha Rahman", "aisha.rahman", "engineer", "L2", "Security", "Security Engineer", "IT", "London HQ"),
    ("karthik", "Karthik Patel", "karthik.patel", "engineer", "L2", "Infrastructure", "Infrastructure Engineer", "IT", "Bengaluru"),
    ("elena", "Elena Rostova", "elena.rostova", "employee", None, None, "Product Designer", "Product Design", "London HQ"),
    ("alex", "Alex Gomez", "alex.gomez", "employee", None, None, "Software Engineer", "Platform Engineering", "Berlin"),
    ("maya", "Maya Okoro", "maya.okoro", "employee", None, None, "Financial Analyst", "Finance", "New York"),
]

ASSETS = [
    # owner key, name, type, service, metadata
    ("elena", "MacBook Pro 14 (LT-0412)", "laptop", "Laptops & Endpoints", {"os": "macOS 14.4 (Sonoma)", "vpn_client": "Cisco AnyConnect 4.10", "mdm": "enrolled"}),
    ("alex", "MacBook Pro 16 (LT-0388)", "laptop", "Laptops & Endpoints", {"os": "macOS 14.5", "vpn_client": "Cisco AnyConnect 4.10", "mdm": "enrolled"}),
    ("alex", "Pixel 8 (MB-1177)", "mobile", "Email & Calendar", {"os": "Android 14", "mail_client": "Outlook"}),
    ("maya", "ThinkPad X1 (LT-0520)", "laptop", "Laptops & Endpoints", {"os": "Windows 11 23H2", "vpn_client": "Cisco AnyConnect 4.10", "mdm": "enrolled"}),
    ("maya", "iPhone 15 (MB-1204)", "mobile", "Identity & SSO", {"os": "iOS 17.5", "authenticator": "Microsoft Authenticator"}),
]

ARTICLES = [
    {
        "title": "VPN troubleshooting (AnyConnect)",
        "summary": "First-line checks when the VPN won't connect or keeps dropping.",
        "category": "Network",
        "subcategory": "VPN",
        "service": "VPN",
        "content": """## Symptoms
- AnyConnect shows "Connection attempt has failed" or stays on "Connecting…".
- Connects, then drops after a few minutes.

## First checks (L1)
1. Confirm the user has general internet access (open any public website).
2. Check the AnyConnect client version. Supported: 4.10 or later.
3. Ask for the exact error text and the time it started.
4. Check whether the user recently changed their password or phone (MFA).
5. Review the authentication log for the user in the VPN admin console.

## Common causes
- **Expired client certificate** — errors mention `CERT_AUTHORITY_INVALID` or "certificate". See the article on VPN certificate expiration.
- **Cached credentials** after a password change — clear saved credentials in AnyConnect and sign in again.
- **Home router blocks UDP 443** — the client stalls on "Connecting…"; switch to the TLS fallback profile.

## Technical details
```
# macOS: collect AnyConnect logs for the engineer
/opt/cisco/anyconnect/bin/dart_cli -dst ~/Desktop/dart_bundle.zip
```
Escalate to Network L2 if the gateway itself is unhealthy or several users are affected.""",
    },
    {
        "title": "VPN certificate expiration and renewal",
        "summary": "Diagnosing and renewing expired VPN client certificates on macOS and Windows.",
        "category": "Network",
        "subcategory": "VPN",
        "service": "VPN",
        "content": """## When to use
The VPN fails during authentication with `CERT_AUTHORITY_INVALID`, "certificate expired", or "no valid certificate". It often appears right after an OS update, which can remove or distrust the client certificate in the keychain.

## Verify
1. macOS: open Keychain Access → login keychain → My Certificates → look for the certificate issued by "Nexa Internal Issuing CA". Check the expiry date.
2. Windows: run `certmgr.msc` → Personal → Certificates → same issuer.
3. If it is missing or expired, the client certificate is the cause.

## Renew (engineer)
1. In the MDM console, find the device and re-push the "VPN client certificate" profile.
2. Ask the user to keep the laptop online for 5 minutes, then restart AnyConnect.
3. Confirm the new certificate appears with a future expiry date.

## Technical details
```
# Check the certificate on macOS (engineer, read-only)
security find-certificate -a -c "vpn-client" -p ~/Library/Keychains/login.keychain-db | openssl x509 -noout -enddate
```

## Confirm
Ask the user to connect to the VPN and open an internal site. Record the new expiry date in the ticket.""",
    },
    {
        "title": "Password reset",
        "summary": "Self-service password reset and when IT needs to help.",
        "category": "Access",
        "subcategory": "Password Reset",
        "service": "Identity & SSO",
        "content": """## Self-service
1. Go to the account portal and choose **Forgot password**.
2. Verify with your registered MFA method.
3. Choose a new password (at least 14 characters, not reused).

## If you're locked out
Accounts lock for 15 minutes after 10 failed attempts. Wait, then try again, or contact IT.

## IT procedure
1. Verify identity with the employee's manager or a video call — never over chat alone.
2. Reset the password in the identity admin console and force change at next sign-in.
3. Remind the user to update the password on their phone and in the VPN client.""",
    },
    {
        "title": "MFA troubleshooting",
        "summary": "Push notifications not arriving, codes rejected, or a new phone.",
        "category": "Access",
        "subcategory": "MFA",
        "service": "Identity & SSO",
        "content": """## Push notifications don't arrive
1. Open the authenticator app and pull to refresh — pending requests appear there.
2. Check the phone allows notifications for the authenticator app.
3. After restoring a phone from backup, re-register the device: the old registration no longer receives pushes.

## Codes are rejected
One-time codes depend on the phone's clock. Turn on automatic date & time.

## New phone
Use the account portal to add the new device before wiping the old one. If the old phone is gone, IT can reset MFA after identity verification.""",
    },
    {
        "title": "Email access issues (Outlook and mobile)",
        "summary": "Outlook asks for a password repeatedly, won't sync, or mobile mail loops.",
        "category": "Email & Collaboration",
        "subcategory": "Email",
        "service": "Email & Calendar",
        "content": """## Check the service first
Sign in to webmail in a browser. If webmail works, the problem is the client, not the mailbox.

## Outlook desktop keeps prompting for a password
1. Close Outlook, remove saved credentials for the mail service from the OS credential store.
2. Reopen Outlook and sign in with SSO.
3. If it persists, create a new Outlook profile.

## Mobile sync loop (Android/iOS)
After OS updates the device partnership can become corrupt. Remove the account from the phone, remove the device partnership in the mail admin console, then add the account again.

## Mailbox full
Mailboxes are 50 GB. Archive old mail or empty Deleted Items.""",
    },
    {
        "title": "Laptop performance",
        "summary": "Slow laptops: indexing, updates, disk space and security scans.",
        "category": "Hardware",
        "subcategory": "Laptop",
        "service": "Laptops & Endpoints",
        "content": """## Quick checks
1. Free disk space: below 10% free causes severe slowdowns.
2. After an OS update, search indexing can run for several hours.
3. Check Activity Monitor / Task Manager for a single process using most CPU.
4. Confirm the laptop is on power and not in a low-power mode.

## Common fixes
- Clear caches and move large files to cloud storage.
- Let indexing finish overnight on power.
- If the security agent (EDR) is scanning continuously, IT can check its status.

Escalate to IT Support for hardware diagnostics if the battery health is poor or the fan is constantly loud.""",
    },
    {
        "title": "Wi-Fi connectivity (Corp-Secure)",
        "summary": "Connecting to Corp-Secure (802.1X) and fixing drop-outs.",
        "category": "Network",
        "subcategory": "Wi-Fi",
        "service": "Corporate Wi-Fi",
        "content": """## How Corp-Secure works
Corp-Secure authenticates the *device* with a certificate installed by MDM. Laptops that aren't enrolled can't join; use the Guest network instead.

## Troubleshooting
1. Confirm the laptop is enrolled in MDM and has the "Corp-Secure Wi-Fi" profile.
2. Forget the network and reconnect.
3. If a new laptop can't join, re-enrol it so the device certificate is installed.
4. Frequent drop-outs in one area: note the room/floor and escalate to Network.""",
    },
    {
        "title": "Certificate expiration (TLS and client certificates)",
        "summary": "How engineers check and renew certificates issued by the internal PKI.",
        "category": "Security",
        "subcategory": "Certificates",
        "service": "Identity & SSO",
        "content": """## Check expiry (read-only)
```
openssl s_client -connect host.internal:443 -servername host.internal </dev/null 2>/dev/null | openssl x509 -noout -dates
```

## Renew a client certificate
Client certificates for VPN and Wi-Fi are delivered by MDM profiles; re-push the profile to the device. Do not issue certificates manually.

## Renew a server certificate
Server certificates are renewed by the Security team through the internal PKI change process. Raise a change ticket and include the hostname, current expiry and owner.""",
    },
    {
        "title": "Production deployment access",
        "summary": "Who can deploy to production and how access is granted or renewed.",
        "category": "Access",
        "subcategory": "Production Access",
        "service": "Deployment Pipeline",
        "content": """## Policy
Deploying to production requires membership in the `deploy-prod` group. Membership is reviewed every quarter and expires automatically if it isn't re-approved.

## Symptoms of missing access
The pipeline fails at the production stage with "permission denied" or "not authorised to approve deployment", while staging still works.

## L1 checks
1. Confirm the user can deploy to staging (rules out general pipeline problems).
2. Check the user's group memberships in the identity console for `deploy-prod`.
3. If membership expired or was never granted, escalate to Applications L2 — L1 cannot grant production access.

## L2 procedure
1. Get approval from the user's manager in the ticket.
2. Add the user to `deploy-prod` for the next review period.
3. Ask the user to re-run the deployment and confirm it passes the production stage.""",
    },
]

# Resolved incidents the AI can retrieve as precedent.
HISTORY = [
    {
        "title": "VPN fails with CERT_AUTHORITY_INVALID after macOS update",
        "description": "Since updating my Mac this morning the VPN won't connect. AnyConnect says CERT_AUTHORITY_INVALID.",
        "requester": "alex", "engineer": "rahul", "team": "Network", "category": "Network", "subcategory": "VPN", "service": "VPN",
        "priority": "P2", "days_ago": 18, "minutes": 42,
        "diagnosis": "The VPN client certificate may have expired or been removed from the keychain by the OS update.",
        "steps": ["Check VPN client status", "Verify certificate validity in Keychain", "Re-push VPN certificate profile via MDM", "Test VPN connection"],
        "resolution": "Client certificate had expired after the macOS update; re-pushed the VPN certificate profile via MDM and confirmed the tunnel connects.",
    },
    {
        "title": "AnyConnect stuck on 'Connecting…' from home network",
        "description": "VPN just spins on Connecting when I'm at home. Works fine in the office.",
        "requester": "maya", "engineer": "rahul", "team": "Network", "category": "Network", "subcategory": "VPN", "service": "VPN",
        "priority": "P3", "days_ago": 33, "minutes": 95,
        "diagnosis": "The home router may be blocking UDP 443 (DTLS), leaving the client unable to finish the handshake.",
        "steps": ["Confirm internet access", "Collect AnyConnect logs", "Switch client to TLS fallback profile", "Test VPN connection"],
        "resolution": "Home router blocked UDP 443; moved the user to the TLS fallback VPN profile and the connection is stable.",
    },
    {
        "title": "VPN rejects login after password change",
        "description": "Changed my password yesterday and now the VPN says my login failed.",
        "requester": "elena", "engineer": "rahul", "team": "Network", "category": "Network", "subcategory": "VPN", "service": "VPN",
        "priority": "P3", "days_ago": 47, "minutes": 25,
        "diagnosis": "AnyConnect may be sending cached credentials from before the password change.",
        "steps": ["Check authentication log", "Clear saved credentials in AnyConnect", "Sign in with new password and MFA"],
        "resolution": "AnyConnect was using cached credentials; cleared them and the user signed in with the new password and MFA.",
    },
    {
        "title": "Corp-Secure Wi-Fi keeps disconnecting on new laptop",
        "description": "My new laptop won't stay on Corp-Secure, it drops every few minutes.",
        "requester": "maya", "engineer": "rahul", "team": "Network", "category": "Network", "subcategory": "Wi-Fi", "service": "Corporate Wi-Fi",
        "priority": "P3", "days_ago": 12, "minutes": 70,
        "diagnosis": "The new laptop may be missing the 802.1X device certificate normally installed through MDM.",
        "steps": ["Check MDM enrolment", "Re-enrol device in MDM", "Reconnect to Corp-Secure"],
        "resolution": "Device certificate was missing; re-enrolled the laptop in MDM which installed the Wi-Fi profile, connection stable.",
    },
    {
        "title": "MFA push notifications not arriving",
        "description": "I don't get the MFA prompt on my phone anymore since I restored it.",
        "requester": "maya", "engineer": "sarah", "team": "IT Support", "category": "Access", "subcategory": "MFA", "service": "Identity & SSO",
        "priority": "P2", "days_ago": 9, "minutes": 30,
        "diagnosis": "The authenticator registration may be tied to the old device image after the phone restore.",
        "steps": ["Check notification permissions", "Remove old device registration", "Re-register authenticator app"],
        "resolution": "Phone restore broke the authenticator registration; removed the old registration and re-registered the app.",
    },
    {
        "title": "Outlook on Android stuck in sync loop",
        "description": "Outlook on my phone keeps syncing forever and never shows new mail.",
        "requester": "alex", "engineer": "priya", "team": "Applications", "category": "Email & Collaboration", "subcategory": "Email", "service": "Email & Calendar",
        "priority": "P3", "days_ago": 26, "minutes": 55,
        "diagnosis": "The mobile device partnership may be corrupted after the Android update.",
        "steps": ["Confirm webmail works", "Remove device partnership", "Re-add account on the phone"],
        "resolution": "Device partnership was corrupt after the OS update; removed it and re-added the account, mail syncing normally.",
    },
    {
        "title": "Cannot deploy to production: permission denied in pipeline",
        "description": "My deployment fails at the production stage with permission denied. Staging works.",
        "requester": "alex", "engineer": "marcus", "l1": "priya", "team": "Applications", "category": "Access", "subcategory": "Production Access", "service": "Deployment Pipeline",
        "priority": "P2", "days_ago": 21, "minutes": 150, "escalated": True,
        "diagnosis": "The user's deploy-prod group membership may have expired at the last quarterly access review.",
        "steps": ["Confirm staging deploy works", "Check deploy-prod membership", "Escalate to Applications L2", "Renew membership after manager approval", "Verify production deploy"],
        "resolution": "deploy-prod membership expired at the quarterly review; renewed after manager approval and the production deploy succeeded.",
    },
    {
        "title": "Laptop extremely slow after update",
        "description": "Everything is painfully slow since the update, even opening Finder.",
        "requester": "elena", "engineer": "sarah", "team": "IT Support", "category": "Hardware", "subcategory": "Laptop", "service": "Laptops & Endpoints",
        "priority": "P4", "days_ago": 40, "minutes": 180,
        "diagnosis": "Search re-indexing after the update combined with low disk space may be saturating the laptop.",
        "steps": ["Check free disk space", "Check indexing status", "Free disk space", "Confirm performance"],
        "resolution": "Spotlight re-indexing plus only 3 GB free disk; freed 40 GB and let indexing finish, performance back to normal.",
    },
]
