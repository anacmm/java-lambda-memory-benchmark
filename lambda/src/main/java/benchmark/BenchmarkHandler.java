package benchmark;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;

@Named("benchmark")
@ApplicationScoped
public class BenchmarkHandler implements RequestHandler<Models.Request, Models.Response> {
    private final S3DatasetReader reader;
    private final ObjectMapper mapper;
    private final Calculation calculation;
    private final AtomicBoolean firstInvocation = new AtomicBoolean(true);

    @Inject
    public BenchmarkHandler(S3DatasetReader reader, ObjectMapper mapper, Calculation calculation) {
        this.reader = reader;
        this.mapper = mapper;
        this.calculation = calculation;
    }

    @Override
    public Models.Response handleRequest(Models.Request request, Context context) {
        long start = System.nanoTime();
        boolean coldStart = firstInvocation.getAndSet(false);
        long s3Ns = 0, cpuNs = 0;
        Long jsonNs = null;
        int bytes = 0;
        Integer count = null;
        String workload = request == null || request.workload() == null ? "cpu" : request.workload();
        String checksum = null, status = "ERROR", errorType = null;
        try {
            if (!workload.equals("cpu") && !workload.equals("io")) {
                throw new IllegalArgumentException("Workload must be cpu or io");
            }
            if (workload.equals("cpu")) count = 0;
            if (request == null || request.bucket() == null || request.bucket().isBlank()
                    || request.key() == null || request.key().isBlank()) {
                throw new IllegalArgumentException("Nonblank bucket and key are required");
            }
            long phase = System.nanoTime();
            byte[] object;
            try { object = reader.read(request.bucket(), request.key()); }
            finally { s3Ns = System.nanoTime() - phase; }
            bytes = object.length;
            Models.Response response;
            if (workload.equals("cpu")) {
                phase = System.nanoTime();
                Models.Dataset dataset;
                try { dataset = mapper.readValue(object, Models.Dataset.class); }
                finally { jsonNs = System.nanoTime() - phase; }
                if (dataset == null) throw new IllegalArgumentException("Dataset is required");
                phase = System.nanoTime();
                try { response = calculation.process(dataset.records()); }
                finally { cpuNs = System.nanoTime() - phase; }
            } else {
                phase = System.nanoTime();
                try { response = IoVerification.process(object); }
                finally { cpuNs = System.nanoTime() - phase; }
            }
            count = response.recordsProcessed();
            checksum = response.checksum();
            status = response.status();
            return response;
        } catch (IOException e) {
            errorType = e.getClass().getSimpleName();
            throw new IllegalArgumentException("Invalid dataset JSON", e);
        } catch (RuntimeException e) {
            errorType = e.getClass().getSimpleName();
            throw e;
        } finally {
            long handlerNs = System.nanoTime() - start;
            var log = mapper.createObjectNode();
            log.put("event", "benchmark_invocation");
            log.put("requestId", context.getAwsRequestId());
            log.put("workload", workload);
            log.put("coldStart", coldStart);
            log.put("memoryMb", context.getMemoryLimitInMB());
            log.put("status", status);
            log.put("recordsProcessed", count);
            log.put("datasetBytes", bytes);
            log.put("objectBytes", bytes);
            log.put("checksum", checksum);
            log.put("errorType", errorType);
            log.put("s3Ms", s3Ns / 1_000_000.0);
            log.put("jsonMs", jsonNs == null ? null : jsonNs / 1_000_000.0);
            log.put("cpuMs", cpuNs / 1_000_000.0);
            log.put("handlerMs", handlerNs / 1_000_000.0);
            context.getLogger().log(log.toString() + "\n");
        }
    }
}
