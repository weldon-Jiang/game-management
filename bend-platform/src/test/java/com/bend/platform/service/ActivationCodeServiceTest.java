package com.bend.platform.service;

import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.Merchant;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.impl.ActivationCodeServiceImpl;
import com.bend.platform.service.impl.VipLevelService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ActivationCodeServiceTest {

    @Mock
    private ActivationCodeMapper activationCodeMapper;

    @Mock
    private ActivationCodeBatchMapper activationCodeBatchMapper;

    @Mock
    private MerchantMapper merchantMapper;

    @Mock
    private VipLevelService vipLevelService;

    @InjectMocks
    private ActivationCodeServiceImpl activationCodeService;

    private ActivationCode activationCode;
    private Merchant merchant;

    @BeforeEach
    void setUp() {
        activationCode = new ActivationCode();
        activationCode.setId("code-001");
        activationCode.setCode("ABC123XYZ789");
        activationCode.setMerchantId("merchant-001");
        activationCode.setSubscriptionType("window_account");
        activationCode.setStatus("unused");
        activationCode.setDiscountPrice(200);

        merchant = new Merchant();
        merchant.setId("merchant-001");
        merchant.setTotalAmount(1000);
        merchant.setVipLevel(3);
    }

    @Test
    void testDeleteUnusedCodeRollsBackMerchantAmountAndVipLevel() {
        when(activationCodeMapper.selectById("code-001")).thenReturn(activationCode);
        when(merchantMapper.selectById("merchant-001")).thenReturn(merchant);
        when(vipLevelService.calculateVipLevel(800)).thenReturn(2);

        activationCodeService.deleteById("code-001");

        assertEquals(800, merchant.getTotalAmount());
        assertEquals(2, merchant.getVipLevel());
        verify(merchantMapper, times(1)).updateById(merchant);
        verify(activationCodeMapper, times(1)).deleteById("code-001");
    }

    @Test
    void testDeleteUnusedPointsCodeAlsoRollsBackMerchantAmountAndVipLevel() {
        activationCode.setSubscriptionType("points");
        activationCode.setDiscountPrice(300);
        when(activationCodeMapper.selectById("code-001")).thenReturn(activationCode);
        when(merchantMapper.selectById("merchant-001")).thenReturn(merchant);
        when(vipLevelService.calculateVipLevel(700)).thenReturn(1);

        activationCodeService.deleteById("code-001");

        assertEquals(700, merchant.getTotalAmount());
        assertEquals(1, merchant.getVipLevel());
        verify(merchantMapper, times(1)).updateById(merchant);
        verify(activationCodeMapper, times(1)).deleteById("code-001");
    }

    @Test
    void testDeleteUnusedCodeClampsTotalAmountToZero() {
        activationCode.setDiscountPrice(1500);
        when(activationCodeMapper.selectById("code-001")).thenReturn(activationCode);
        when(merchantMapper.selectById("merchant-001")).thenReturn(merchant);
        when(vipLevelService.calculateVipLevel(0)).thenReturn(0);

        activationCodeService.deleteById("code-001");

        assertEquals(0, merchant.getTotalAmount());
        assertEquals(0, merchant.getVipLevel());
        verify(merchantMapper, times(1)).updateById(merchant);
        verify(activationCodeMapper, times(1)).deleteById("code-001");
    }

    @Test
    void testDeleteUsedCodeThrowsAndDoesNotMutateData() {
        activationCode.setStatus("used");
        when(activationCodeMapper.selectById("code-001")).thenReturn(activationCode);

        RuntimeException ex = assertThrows(RuntimeException.class, () -> activationCodeService.deleteById("code-001"));

        assertEquals("已使用的激活码无法删除", ex.getMessage());
        verify(merchantMapper, never()).selectById(any());
        verify(merchantMapper, never()).updateById(any());
        verify(activationCodeMapper, never()).deleteById(any(String.class));
    }

    @Test
    void testDeleteMissingCodeThrows() {
        when(activationCodeMapper.selectById("code-001")).thenReturn(null);

        RuntimeException ex = assertThrows(RuntimeException.class, () -> activationCodeService.deleteById("code-001"));

        assertEquals("激活码不存在", ex.getMessage());
        verify(merchantMapper, never()).selectById(any());
        verify(merchantMapper, never()).updateById(any());
        verify(activationCodeMapper, never()).deleteById(any(String.class));
    }

    @Test
    void testDeleteCodeWithMissingMerchantThrowsAndKeepsActivationCode() {
        when(activationCodeMapper.selectById("code-001")).thenReturn(activationCode);
        when(merchantMapper.selectById("merchant-001")).thenReturn(null);

        RuntimeException ex = assertThrows(RuntimeException.class, () -> activationCodeService.deleteById("code-001"));

        assertEquals("激活码关联的商户不存在", ex.getMessage());
        verify(merchantMapper, never()).updateById(any());
        verify(activationCodeMapper, never()).deleteById(any(String.class));
    }
}
