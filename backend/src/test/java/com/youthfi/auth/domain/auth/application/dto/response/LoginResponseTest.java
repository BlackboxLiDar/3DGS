package com.youthfi.auth.domain.auth.application.dto.response;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

@DisplayName("LoginResponse 테스트")
class LoginResponseTest {

    @Test
    @DisplayName("유효한 LoginResponse 생성")
    void createValidLoginResponse() {
        // given
        String accessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";
        String refreshToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";

        // when
        LoginResponse response = new LoginResponse(accessToken, refreshToken);

        // then
        assertNotNull(response);
        assertEquals(accessToken, response.accessToken());
        assertEquals(refreshToken, response.refreshToken());
    }

    @Test
    @DisplayName("null 토큰으로 LoginResponse 생성")
    void createLoginResponseWithNullTokens() {
        // when
        LoginResponse response = new LoginResponse(null, null);

        // then
        assertNotNull(response);
        assertNull(response.accessToken());
        assertNull(response.refreshToken());
    }

    @Test
    @DisplayName("빈 문자열 토큰으로 LoginResponse 생성")
    void createLoginResponseWithEmptyTokens() {
        // given
        String accessToken = "";
        String refreshToken = "";

        // when
        LoginResponse response = new LoginResponse(accessToken, refreshToken);

        // then
        assertNotNull(response);
        assertEquals(accessToken, response.accessToken());
        assertEquals(refreshToken, response.refreshToken());
    }

    @Test
    @DisplayName("다양한 토큰 형식으로 LoginResponse 생성")
    void createLoginResponseWithVariousTokenFormats() {
        String[] accessTokens = {
                "simple.token",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                "very.long.token.with.many.parts.and.dots",
                "token-with-dashes",
                "token_with_underscores",
                "token123with456numbers789"
        };

        String[] refreshTokens = {
                "refresh.simple.token",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                "refresh.very.long.token.with.many.parts.and.dots",
                "refresh-token-with-dashes",
                "refresh_token_with_underscores",
                "refresh123token456with789numbers"
        };

        for (String accessToken : accessTokens) {
            for (String refreshToken : refreshTokens) {
                // when
                LoginResponse response = new LoginResponse(accessToken, refreshToken);

                // then
                assertNotNull(response);
                assertEquals(accessToken, response.accessToken());
                assertEquals(refreshToken, response.refreshToken());
            }
        }
    }

    @Test
    @DisplayName("LoginResponse equals 테스트")
    void testLoginResponseEquals() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        LoginResponse response1 = new LoginResponse(accessToken, refreshToken);
        LoginResponse response2 = new LoginResponse(accessToken, refreshToken);
        LoginResponse response3 = new LoginResponse("different.access.token", refreshToken);
        LoginResponse response4 = new LoginResponse(accessToken, "different.refresh.token");

        // when & then
        assertEquals(response1, response2);
        assertNotEquals(response1, response3);
        assertNotEquals(response1, response4);
        assertNotEquals(response3, response4);
    }

    @Test
    @DisplayName("LoginResponse hashCode 테스트")
    void testLoginResponseHashCode() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        LoginResponse response1 = new LoginResponse(accessToken, refreshToken);
        LoginResponse response2 = new LoginResponse(accessToken, refreshToken);
        LoginResponse response3 = new LoginResponse("different.access.token", refreshToken);

        // when & then
        assertEquals(response1.hashCode(), response2.hashCode());
        assertNotEquals(response1.hashCode(), response3.hashCode());
    }

    @Test
    @DisplayName("LoginResponse toString 테스트")
    void testLoginResponseToString() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        LoginResponse response = new LoginResponse(accessToken, refreshToken);

        // when
        String toString = response.toString();

        // then
        assertNotNull(toString);
        assertTrue(toString.contains("LoginResponse"));
        assertTrue(toString.contains(accessToken));
        assertTrue(toString.contains(refreshToken));
    }

    @Test
    @DisplayName("LoginResponse record 특성 테스트")
    void testLoginResponseRecordCharacteristics() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        LoginResponse response = new LoginResponse(accessToken, refreshToken);

        // when & then
        // Record는 자동으로 equals, hashCode, toString을 생성
        assertNotNull(response);
        
        // Record의 컴포넌트 접근
        assertEquals(accessToken, response.accessToken());
        assertEquals(refreshToken, response.refreshToken());
        
        // Record는 final 클래스
        assertTrue(LoginResponse.class.isRecord());
    }
}
