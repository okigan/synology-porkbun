To use this script with a Synology router:

1. Save the script on your Synology device (e.g., as `/usr/syno/bin/ddns/porkbun.sh`).
2. Make it executable: `chmod +x /usr/syno/bin/ddns/porkbun.sh`
3. Add an entry to the `/etc/ddns_provider.conf` file (you may need to create this file if it doesn't exist):

```
[Porkbun]
        modulepath = /usr/syno/bin/ddns/porkbun.sh
        queryurl = Porkbun
```

4. In the Synology router's DDNS settings, you should now be able to select "Porkbun" as a provider and enter your API key as the username and your Secret key as the password.

This script should now be compatible with the Synology router's custom DDNS system while still performing the Porkbun DNS update. Let me know if you need any further modifications or explanations!

