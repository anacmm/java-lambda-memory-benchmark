package benchmark;

import io.quarkus.runtime.annotations.RegisterForReflection;
import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.List;

public final class Models {
    private Models() {}

    @RegisterForReflection
    public record Request(String workload, String bucket, String key) {
        public Request {
            if (workload == null) workload = "cpu";
        }

        // Keep existing Java callers and requests without workload compatible with CPU.
        public Request(String bucket, String key) {
            this("cpu", bucket, key);
        }
    }

    @RegisterForReflection
    public record DataRecord(long id, long value, String category) {}

    @RegisterForReflection
    public record Dataset(List<DataRecord> records) {}

    @RegisterForReflection
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Response(Integer recordsProcessed, String checksum, String status, Long objectBytes) {
        public Response(int recordsProcessed, String checksum, String status) {
            this(recordsProcessed, checksum, status, null);
        }
    }
}
