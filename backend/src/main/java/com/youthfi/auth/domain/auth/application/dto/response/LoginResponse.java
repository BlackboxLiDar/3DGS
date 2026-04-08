package com.youthfi.auth.domain.auth.application.dto.response;

public record LoginResponse(
        String accessToken,
        String refreshToken
) {}