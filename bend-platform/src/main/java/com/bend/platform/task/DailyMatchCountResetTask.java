package com.bend.platform.task;

import com.bend.platform.entity.GameAccount;
import com.bend.platform.service.GameAccountService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class DailyMatchCountResetTask {

    private final GameAccountService gameAccountService;

    @Scheduled(cron = "0 0 0 * * ?")
    public void resetDailyMatchCount() {
        log.info("Starting daily match count reset task...");

        try {
            List<GameAccount> allAccounts = gameAccountService.findAllByStreamingId(null);
            
            if (allAccounts.isEmpty()) {
                log.info("No game accounts found to reset");
                return;
            }

            int resetCount = 0;
            for (GameAccount ga : allAccounts) {
                if (ga.getTodayMatchCount() != null && ga.getTodayMatchCount() > 0) {
                    ga.setTodayMatchCount(0);
                    gameAccountService.update(ga.getId(), ga);
                    resetCount++;
                }
            }

            log.info("Daily match count reset completed. Reset {} of {} accounts", 
                    resetCount, allAccounts.size());
            
        } catch (Exception e) {
            log.error("Error during daily match count reset", e);
        }
    }
}