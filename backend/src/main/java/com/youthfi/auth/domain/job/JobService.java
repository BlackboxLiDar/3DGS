package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Sort;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Slf4j @Service @RequiredArgsConstructor
public class JobService {
    private final ReconstructionJobRepository jobRepository;
    private final RedisTemplate<String, Object> redisTemplate;
    private final JobQueue jobQueue;

    @Transactional
    public String createJob(User user, String filePath) {
        String jobId = UUID.randomUUID().toString();
        JobEntity job = JobEntity.builder()
                .jobId(jobId).user(user).originalFileName(filePath)
                .status(JobStatus.PENDING).progress(0).currentStep("업로드 완료")
                .build();
        
        jobRepository.save(job);
        syncRedis(job);
        jobQueue.push(jobId);
        return jobId;
    }

    public List<JobEntity> searchJobs(User user, String title, JobStatus status, String sortBy) {
        // 정렬 기준 설정: sortBy가 'incidentDate'면 사고날짜, 아니면 생성날짜
        String sortField = "incidentDate".equals(sortBy) ? "incidentDate" : "createdAt";
        Sort sort = Sort.by(Sort.Direction.DESC, sortField);

        if (title != null && !title.isEmpty()) {
            return jobRepository.findByUserUserIdAndCustomTitleContaining(user.getUserId(), title, sort);
        }
        if (status != null) {
            return jobRepository.findByUserUserIdAndStatus(user.getUserId(), status, sort);
        }
        return jobRepository.findByUserUserId(user.getUserId(), sort);
    }

    @Transactional
    public void updateProgress(String jobId, int progress, String step, String status) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            try {
                entity.updateProgress(progress, step, JobStatus.valueOf(status.toUpperCase()));
                jobRepository.save(entity);
                syncRedis(entity);
            } catch (Exception e) { log.error("Status Update Error: {}", status); }
        });
    }

    public JobStatusResponse getJob(String jobId) {
        Object cached = redisTemplate.opsForValue().get("job:" + jobId);
        if (cached instanceof JobStatusResponse) return (JobStatusResponse) cached;
        return jobRepository.findById(jobId).map(JobStatusResponse::from).orElse(null);
    }

    @Transactional
    public void updateCustomTitle(String jobId, String newTitle, User user) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            if (entity.getUser().getUserId().equals(user.getUserId())) {
                entity.updateTitle(newTitle);
                syncRedis(entity);
            }
        });
    }

    @Transactional
    public void saveTargetIds(String jobId, List<Integer> targetIds, User user) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            if (entity.getUser().getUserId().equals(user.getUserId())) {
                entity.assignTargets(targetIds);
                syncRedis(entity);
            }
        });
    }

    private void syncRedis(JobEntity entity) {
        redisTemplate.opsForValue().set("job:" + entity.getJobId(), JobStatusResponse.from(entity));
    }
}