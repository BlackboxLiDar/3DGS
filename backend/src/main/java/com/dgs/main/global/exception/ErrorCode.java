package com.dgs.main.global.exception;

import lombok.Getter;
import org.springframework.http.HttpStatus;

@Getter
public enum ErrorCode {

    // Common
    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "C001", "잘못된 입력값입니다."),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "C002", "서버 내부 오류가 발생했습니다."),

    // Security & Auth
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "A001", "인증이 필요합니다."),
    FORBIDDEN(HttpStatus.FORBIDDEN, "A002", "접근 권한이 없습니다."),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "A003", "유효하지 않거나 만료된 토큰입니다."),

    // Storage / File
    FILE_SIZE_EXCEEDED(HttpStatus.BAD_REQUEST, "F001", "허용된 파일 크기를 초과했습니다."),
    INVALID_FILE_EXT(HttpStatus.BAD_REQUEST, "F002", "지원하지 않는 파일 확장자입니다."),
    GCS_UPLOAD_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "F003", "GCS 스토리지 업로드 티켓 발급에 실패했습니다."),

    // Task
    TASK_NOT_FOUND(HttpStatus.NOT_FOUND, "T001", "해당 작업을 찾을 수 없습니다."),
    TASK_ALREADY_IN_PROGRESS(HttpStatus.CONFLICT, "T002", "이미 진행 중인 작업이 있어 새 작업을 시작할 수 없습니다."),
    QUOTA_EXCEEDED(HttpStatus.TOO_MANY_REQUESTS, "T003", "일일 최대 변환(AI 처리) 횟수를 초과해 더 이상 요청할 수 없습니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;

    ErrorCode(HttpStatus status, String code, String message) {
        this.status = status;
        this.code = code;
        this.message = message;
    }
}
