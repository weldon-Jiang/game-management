$sql1 = "UPDATE streaming_account SET task_status = 'idle', agent_id = NULL WHERE id = '575f67249be844b0730249b1aab38bb0'"
$sql2 = "UPDATE game_account SET status = 'idle', agent_id = NULL WHERE streaming_id = '575f67249be844b0730249b1aab38bb0'"

docker exec bend-xbox-mysql mysql -u root -p'D@GAMECeKfidb' -D bend_platform -e $sql1
docker exec bend-xbox-mysql mysql -u root -p'D@GAMECeKfidb' -D bend_platform -e $sql2

Write-Host "Status reset completed"