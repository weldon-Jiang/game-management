#!/usr/bin/env bash
# 本地三端验证 - 准备脚本
# 在仓库根 d:/auto-xbox/team-management 用 Git Bash 运行:  bash deploy/standalone/local-setup.sh
# 作用: 登录总控签 License + 建分控库 + 导 schema + 导商户数据
# 前置: 总控 Docker 已起且已重建(含 License 代码)
set -e
MASTER=http://localhost:8060
MERCHANT=f5d927c40f87f57ef0f4a484d8a823e9   # 系统商户(测试用)
TENANT_DB=bend_platform_tenant

# ====== 填这 2 个值(从 docker/.env 看;密码含 $ @ 等特殊字符必须用单引号) ======
ADMIN_PWD='123456'
MYSQL_PWD='D@GAMECeKfidb'   # 例: 'D$U@GAMECeKfidb'
# =============================================================================

echo "[1/4] 登录总控..."
LOGIN=$(curl -s -X POST "$MASTER/api/auth/login" -H "Content-Type: application/json" \
  -d "{\"loginKey\":\"admin\",\"password\":\"$ADMIN_PWD\"}")
TOKEN=$(echo "$LOGIN" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('token',''))" 2>/dev/null || true)
if [ -z "$TOKEN" ]; then
  echo "  登录失败,响应: $LOGIN"
  echo "  → 若不知道 admin 密码,把响应贴给我,我帮你用 AES 重置"
  exit 1
fi
echo "  token 获取成功"

echo "[2/4] 签 License..."
LIC=$(curl -s -X POST "$MASTER/api/licenses" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"merchantId\":\"$MERCHANT\",\"expireAt\":\"2027-07-16T00:00:00\",\"maxAgents\":5,\"maxTasks\":50}")
echo "  $LIC"
LICENSE_KEY=$(echo "$LIC" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('licenseKey',''))" 2>/dev/null || true)
LICENSE_SECRET=$(echo "$LIC" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('licenseSecret',''))" 2>/dev/null || true)
if [ -z "$LICENSE_KEY" ]; then echo "  签 License 失败,贴上面响应给我"; exit 1; fi
echo "  licenseKey=$LICENSE_KEY"
echo "  licenseSecret=$LICENSE_SECRET"

echo "[3/4] 建分控库 + 导 schema..."
docker exec bend-xbox-mysql mysql -u root -p"$MYSQL_PWD" -e "CREATE DATABASE IF NOT EXISTS $TENANT_DB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>&1 | grep -vi "warning" || true
docker exec -i bend-xbox-mysql mysql -u root -p"$MYSQL_PWD" "$TENANT_DB" < bend-platform/db/schema.sql 2>&1 | grep -vi "warning" || true
echo "  schema 导入完成"

echo "[4/4] 导商户数据(调总控 export-data 接口)..."
curl -s -H "Authorization: Bearer $TOKEN" "$MASTER/api/merchants/$MERCHANT/export-data" -o merchant_data.sql
docker exec -i bend-xbox-mysql mysql -u root -p"$MYSQL_PWD" "$TENANT_DB" < merchant_data.sql 2>&1 | grep -vi "warning" || true
echo "  商户数据导入完成"

echo ""
echo "========== 准备完成 =========="
echo "把下面两个值贴给我(填到分控启动命令):"
echo "LICENSE_KEY=$LICENSE_KEY"
echo "LICENSE_SECRET=$LICENSE_SECRET"
echo "分控库 $TENANT_DB 已就绪(含 schema + 该商户数据)"
