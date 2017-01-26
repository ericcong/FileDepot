package boot;

import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.*;
import org.springframework.stereotype.*;
import org.springframework.ui.*;

import org.springframework.web.servlet.view.*;

import javax.servlet.http.*;
import org.springframework.http.*;
import org.springframework.web.client.*;
import org.springframework.boot.json.*;

import java.util.*;

import org.slf4j.*;

@CrossOrigin(origins="*")
@Controller
public class WebController {

    private static final Logger log = LoggerFactory.getLogger(WebController.class);

    @RequestMapping(value="/viewfile", method=RequestMethod.GET)
    public RedirectView view(
    	@RequestParam(value="id", required=true) String id
    ) {
        log.info(id);
        String url = retrieve(login(), id);
        log.info(url);
        return new RedirectView(url);
    }

    @RequestMapping(value="/uploadfile", method=RequestMethod.POST, consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> upload(
        @RequestBody String body
    ) {
        String locker = reserve(login(), body);
        log.info(locker);
        HttpHeaders responseHeaders = new HttpHeaders();
        responseHeaders.setContentType(MediaType.APPLICATION_JSON);
        return new ResponseEntity<String>(locker, 
            responseHeaders, HttpStatus.OK);
    }

    private String login() {
        // API need to make sure clean up expired sessions
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.postForEntity(
            "http://lowcost-env.rsgwu3uhma.us-east-1.elasticbeanstalk.com/login", 
            "{ \"type\": \"CAS\", \"cred\": { \"id\": \"test\" } }",
            String.class);
        Map<String, Object> m = JsonParserFactory.getJsonParser()
            .parseMap(response.getBody());
        return m.get("session_id").toString();        
    }

    private String reserve(String sessionId, String request) {
        Map<String, Object> m = JsonParserFactory.getJsonParser()
            .parseMap(request);
        // check file type
        // check file size
        // set expiration time
        // optionaly remove file name, so random name will be used
        m.put("session_id", ""+sessionId);
        log.info(m.toString());
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.postForEntity(
            "http://lowcost-env.rsgwu3uhma.us-east-1.elasticbeanstalk.com/lockers", 
            m,
            String.class);
        return response.getBody();
    }

    private String retrieve(String sessionId, String lockerId) {
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.getForEntity(
            "http://lowcost-env.rsgwu3uhma.us-east-1.elasticbeanstalk.com/lockers/"+
            lockerId+"?session_id="+sessionId, 
            String.class);
        log.info(response.getBody());
        Map<String, Object> m = JsonParserFactory.getJsonParser()
            .parseMap(response.getBody());
        log.info(m.get("packages").toString());
        // API support multi-package per locker, here we use only one    
        return ((Map)((List)m.get("packages")).get(0)).get("download_url").toString();       
    }

}
