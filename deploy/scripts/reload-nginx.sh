#!/bin/sh
# Reload nginx only if its configuration is valid.
/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx
