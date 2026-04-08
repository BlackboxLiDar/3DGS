package com.youthfi.auth.domain.auth.application.usecase;

import java.time.Duration;
import java.util.Optional;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.youthfi.auth.domain.auth.application.dto.request.LoginRequest;
import com.youthfi.auth.domain.auth.application.dto.request.SignUpRequest;
import com.youthfi.auth.domain.auth.application.dto.request.TokenReissueRequest;
import com.youthfi.auth.domain.auth.application.dto.response.LoginResponse;
import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.domain.auth.domain.repository.UserRepository;
import com.youthfi.auth.domain.auth.domain.service.RefreshTokenService;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.exception.code.status.AuthErrorStatus;
import com.youthfi.auth.global.security.TokenProvider;

import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;

@Service
@Transactional
@RequiredArgsConstructor
public class UserAuthUseCase {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final TokenProvider tokenProvider;
    private final RefreshTokenService refreshTokenService;

    public void signUp(SignUpRequest request) {
        if (userRepository.existsByUserId(request.userId())) {
            throw new RestApiException(AuthErrorStatus.ALREADY_REGISTERED_USER_ID);
        }
        User user = User.builder()
                .userId(request.userId())
                .password(passwordEncoder.encode(request.password()))
                .email(request.email())
                .name(request.name())
                .build();
        userRepository.save(user);
    }

    public LoginResponse login(LoginRequest request) {
        User user = userRepository.findByUserId(request.userId())
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.LOGIN_ERROR));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new RestApiException(AuthErrorStatus.LOGIN_ERROR);
        }

        String accessToken = tokenProvider.createAccessToken(user.getUserId());
        String refreshToken = tokenProvider.createRefreshToken(user.getUserId());
        refreshTokenService.saveRefreshToken(user.getUserId(), refreshToken, Duration.ofDays(14));

        return new LoginResponse(accessToken, refreshToken);
    }

    // 🔥 4개 테스트 실패를 잡는 핵심 로직 (순서가 생명입니다!)
    public TokenReissueResponse reissueToken(TokenReissueRequest request) {
        String refreshToken = request.refreshToken();

        // 1. Null 토큰 체크 (테스트: null 토큰으로 재발급 시도 시 예외 발생)
        if (refreshToken == null) {
            throw new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN);
        }

        // 2. 토큰에서 ID 추출 시도 (이게 선행되어야 테스트가 만족함)
        String userId = tokenProvider.getId(refreshToken)
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN));

        // 3. 사용자 존재 여부 확인 (테스트: 사용자를 찾을 수 없을 때 예외 발생)
        if (!userRepository.existsByUserId(userId)) {
            throw new RestApiException(AuthErrorStatus.LOGIN_ERROR);
        }

        // 4. 리프레시 토큰 존재 확인 (테스트: 리프레시 토큰이 존재하지 않을 때 예외 발생)
        if (!refreshTokenService.isExist(refreshToken, userId)) {
            throw new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN);
        }

        // 5. 만료 시간 체크 (테스트: 리프레시 토큰 만료 시간을 가져올 수 없을 때)
        Duration duration = tokenProvider.getRemainingDuration(refreshToken)
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.EXPIRED_MEMBER_JWT));

        // 6. 재발급 진행
        refreshTokenService.deleteRefreshToken(userId);
        String newAccessToken = tokenProvider.createAccessToken(userId);
        String newRefreshToken = tokenProvider.createRefreshToken(userId);
        refreshTokenService.saveRefreshToken(userId, newRefreshToken, duration);

        return new TokenReissueResponse(newAccessToken, newRefreshToken);
    }

    public void logout(HttpServletRequest request) {
        tokenProvider.getToken(request).ifPresent(token -> {
            if (tokenProvider.validateToken(token)) {
                tokenProvider.getId(token).ifPresent(refreshTokenService::deleteRefreshToken);
            }
        });
    }

    public void logout(String userId) {
        refreshTokenService.deleteRefreshToken(userId);
    }

    public String verifyToken(HttpServletRequest request) {
        Optional<String> tokenOpt = tokenProvider.getToken(request);
        if (tokenOpt.isEmpty()) throw new RestApiException(AuthErrorStatus.EMPTY_JWT);
        
        String token = tokenOpt.get();
        if (tokenProvider.validateToken(token)) {
            return tokenProvider.getId(token)
                    .orElseThrow(() -> new RestApiException(AuthErrorStatus.INVALID_ACCESS_TOKEN));
        }
        throw new RestApiException(AuthErrorStatus.INVALID_ACCESS_TOKEN);
    }
}